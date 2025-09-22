"""Content generation module for Xiaohongshu posts."""
from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Protocol

from .logging_utils import configure_logging

logger = logging.getLogger(__name__)


class ContentGenerationError(RuntimeError):
    """Raised when the content generation pipeline fails."""


class TextGenerationClient(Protocol):
    """Protocol for text generation providers such as GPT/Claude."""

    def generate_text(self, prompt: str) -> str:
        """Generate text for the supplied prompt."""


class ImageGenerationClient(Protocol):
    """Protocol for image generation providers such as DALL·E/Stable Diffusion."""

    def generate_image(self, prompt: str, output_path: Path) -> Path:
        """Generate an image and save it to ``output_path``."""


@dataclass(slots=True)
class PromptBuilder:
    """Centralised prompt templates for Xiaohongshu styled content."""

    tone: str = "口语化、活泼"
    emojis: Iterable[str] = field(
        default_factory=lambda: ["✨", "😍", "💡", "📌", "🔥", "🥰", "🌟", "🎯", "🧡", "🎉"]
    )
    min_tags: int = 3
    max_tags: int = 5

    def _sample_emojis(self) -> str:
        emojis = list(self.emojis)
        if not emojis:
            return ""
        k = min(3, len(emojis))
        return "".join(random.sample(emojis, k))

    def build_text_prompt(self, keyword: str) -> str:
        """Build the LLM prompt for Xiaohongshu styled copywriting."""

        emoji_block = self._sample_emojis()
        instructions = {
            "keyword": keyword,
            "tone": self.tone,
            "emojis": emoji_block,
            "min_tags": self.min_tags,
            "max_tags": self.max_tags,
        }
        prompt = f"""
你是一名资深小红书运营，请根据以下要求生成一份内容包：

- 主题关键词：{instructions['keyword']}
- 文风：{instructions['tone']}
- 文案需自然融入至少 2 个 emoji，可优先考虑：{instructions['emojis']}
- 标题要求醒目、吸引点击，18 个汉字以内
- 正文包含引入、干货和行动号召三个部分
- 至少提供 {instructions['min_tags']} 个、至多 {instructions['max_tags']} 个话题标签（# 开头）
- 以 JSON 返回，字段：title, body, tags (字符串数组)
- body 段落之间请使用换行分隔

示例返回格式：
{{
  "title": "...",
  "body": "段落1\n\n段落2",
  "tags": ["#tag1", "#tag2"]
}}
"""
        return prompt.strip()

    def build_image_prompt(self, keyword: str, title: str, body: str) -> str:
        """Build prompt text for image generation."""

        summary = body.splitlines()[0].strip() if body.strip() else keyword
        prompt = (
            f"High quality vibrant cover illustration for a Xiaohongshu post. "
            f"Topic: {keyword}. Title: {title}. Highlight: {summary}. "
            "Use bright colors, portrait orientation, modern flat design, no text on image."
        )
        return prompt


@dataclass(slots=True)
class ContentPackage:
    """Normalized representation of generated content."""

    keyword: str
    title: str
    body: str
    tags: List[str]
    image_path: Path

    def to_json(self) -> str:
        return json.dumps(
            {
                "keyword": self.keyword,
                "title": self.title,
                "body": self.body,
                "tags": self.tags,
                "image_path": str(self.image_path),
            },
            ensure_ascii=False,
            indent=2,
        )


@dataclass(slots=True)
class ContentGenerator:
    """Pipeline orchestrating text and image generation."""

    text_client: TextGenerationClient
    image_client: ImageGenerationClient
    prompt_builder: PromptBuilder = field(default_factory=PromptBuilder)
    output_dir: Path = field(default_factory=lambda: Path("data/content_packages"))

    def __post_init__(self) -> None:
        configure_logging()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, keyword: str) -> ContentPackage:
        """Generate a Xiaohongshu content package for ``keyword``."""

        logger.info("Generating content for keyword '%s'", keyword)
        text_prompt = self.prompt_builder.build_text_prompt(keyword)
        logger.debug("Text prompt prepared: %s", text_prompt)

        try:
            raw_response = self.text_client.generate_text(text_prompt)
        except Exception as exc:  # pragma: no cover - defensive catch
            logger.exception("Text generation failed: %s", exc)
            raise ContentGenerationError("文本生成失败") from exc

        logger.debug("Raw text response: %s", raw_response)
        payload = self._parse_text_response(raw_response)
        title = payload["title"].strip()
        body = payload["body"].strip()
        tags = self._normalize_tags(payload["tags"])

        timestamp = int(time.time())
        safe_keyword = re.sub(r"[^\w\-]+", "_", keyword).strip("_") or "note"
        image_filename = f"{safe_keyword}_{timestamp}.png"
        image_path = self.output_dir / image_filename

        image_prompt = self.prompt_builder.build_image_prompt(keyword, title, body)
        logger.debug("Image prompt prepared: %s", image_prompt)

        try:
            generated_image_path = self.image_client.generate_image(image_prompt, image_path)
        except Exception as exc:  # pragma: no cover - defensive catch
            logger.exception("Image generation failed: %s", exc)
            raise ContentGenerationError("图片生成失败") from exc

        logger.info("Content package generated: title='%s', image='%s'", title, generated_image_path)
        return ContentPackage(keyword=keyword, title=title, body=body, tags=tags, image_path=generated_image_path)

    @staticmethod
    def _parse_text_response(raw_response: str) -> dict:
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ContentGenerationError("无法解析模型返回的 JSON") from exc

        required_keys = {"title", "body", "tags"}
        if not required_keys.issubset(payload):
            missing = required_keys.difference(payload)
            raise ContentGenerationError(f"返回结果缺少字段: {', '.join(sorted(missing))}")

        if not isinstance(payload["tags"], list):
            raise ContentGenerationError("tags 字段必须是数组")
        return payload

    @staticmethod
    def _normalize_tags(tags: Iterable[str]) -> List[str]:
        normalized = []
        for tag in tags:
            if not tag:
                continue
            value = str(tag).strip()
            if not value:
                continue
            if not value.startswith("#"):
                value = f"#{value}"
            normalized.append(value)
        if not normalized:
            raise ContentGenerationError("模型未返回有效的话题标签")
        return normalized


class OpenAITextClient:
    """OpenAI GPT based text generator."""

    def __init__(self, client: Optional["OpenAI"] = None, model: str = "gpt-4o-mini") -> None:
        try:  # pragma: no cover - simple import wrapper
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - import guard
            raise RuntimeError("openai 库未安装，请先执行 pip install openai") from exc

        self._client = client or OpenAI()
        self._model = model

    def generate_text(self, prompt: str) -> str:
        response = self._client.responses.create(
            model=self._model,
            input=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        # OpenAI responses API returns content list; we expect JSON text
        content = response.output[0].content[0].text  # type: ignore[attr-defined]
        return content


class OpenAIImageClient:
    """OpenAI Images (DALL·E) based image generator."""

    def __init__(self, client: Optional["OpenAI"] = None, model: str = "gpt-image-1") -> None:
        try:  # pragma: no cover - import guard
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai 库未安装，请先执行 pip install openai") from exc

        self._client = client or OpenAI()
        self._model = model

    def generate_image(self, prompt: str, output_path: Path) -> Path:
        response = self._client.images.generate(
            model=self._model,
            prompt=prompt,
            size="1024x1024",
            response_format="b64_json",
        )
        image_b64 = response.data[0].b64_json  # type: ignore[attr-defined]
        if not image_b64:
            raise ContentGenerationError("OpenAI 未返回图片数据")

        import base64

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as fh:
            fh.write(base64.b64decode(image_b64))
        return output_path


__all__ = [
    "ContentGenerationError",
    "ContentGenerator",
    "ContentPackage",
    "ImageGenerationClient",
    "OpenAIImageClient",
    "OpenAITextClient",
    "PromptBuilder",
    "TextGenerationClient",
]
