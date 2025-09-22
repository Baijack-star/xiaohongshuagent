import json
from pathlib import Path

import pytest

from xiaohongshuagent.content_generation import (
    ContentGenerationError,
    ContentGenerator,
    ContentPackage,
    PromptBuilder,
)


class StubTextClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts = []

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class StubImageClient:
    def __init__(self) -> None:
        self.calls = []

    def generate_image(self, prompt: str, output_path: Path) -> Path:
        self.calls.append((prompt, output_path))
        output_path.write_bytes(b"fake-image-data")
        return output_path


@pytest.fixture()
def prompt_builder() -> PromptBuilder:
    return PromptBuilder(emojis=["✨", "😍", "🎉"])


def test_content_generator_builds_package(tmp_path: Path, prompt_builder: PromptBuilder) -> None:
    response = json.dumps(
        {
            "title": "超级省心的收纳技巧",
            "body": "第一段\n\n第二段",
            "tags": ["#收纳", "生活技巧"],
        },
        ensure_ascii=False,
    )
    generator = ContentGenerator(
        text_client=StubTextClient(response),
        image_client=StubImageClient(),
        prompt_builder=prompt_builder,
        output_dir=tmp_path,
    )

    package = generator.generate("收纳")

    assert isinstance(package, ContentPackage)
    assert package.title == "超级省心的收纳技巧"
    assert package.body.startswith("第一段")
    assert package.tags == ["#收纳", "#生活技巧"]
    assert package.image_path.exists()
    assert package.image_path.read_bytes() == b"fake-image-data"


def test_content_generator_invalid_json(tmp_path: Path, prompt_builder: PromptBuilder) -> None:
    generator = ContentGenerator(
        text_client=StubTextClient("not-json"),
        image_client=StubImageClient(),
        prompt_builder=prompt_builder,
        output_dir=tmp_path,
    )

    with pytest.raises(ContentGenerationError):
        generator.generate("家居")


def test_prompt_builder_contains_keyword(prompt_builder: PromptBuilder) -> None:
    prompt = prompt_builder.build_text_prompt("旅行")
    assert "旅行" in prompt
    assert "JSON" in prompt
