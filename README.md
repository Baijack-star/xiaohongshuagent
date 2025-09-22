# 小红书数字员工 MVP

该项目旨在构建一个可扩展的「小红书自媒体数字员工」原型，包含登录、内容生成、发帖、评论抓取、自动回复和日志报告等模块。目前已实现：

- **模块 1：登录与会话管理**
- **模块 2：内容生成模块**

## 环境要求

- Python 3.9+
- [Playwright](https://playwright.dev/python/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)

安装依赖：

```bash
pip install -r requirements.txt
playwright install chromium
```

如需调用 OpenAI 接口，请在运行前设置环境变量：

```bash
export OPENAI_API_KEY="sk-..."
```

## 模块 1：登录与会话管理

`XiaohongshuSessionManager` 使用 Playwright 启动浏览器，实现扫码登录/导入 Cookie 的能力，并负责本地 Session 的持久化。

### 主要能力

- 支持扫码登录：打开创作平台登录页，等待扫码完成后自动保存 Cookie。
- 支持导入 Cookie：可从 JSON 文件或 Python 对象导入既有 Cookie。
- Session 持久化：统一保存在 `data/xiaohongshu_session.json`，包含 Cookie 与时间戳。
- 登录检测：支持检查本地是否已有 Cookie，辅助后续模块判断是否需重新登录。

### 使用示例

```python
from xiaohongshuagent import XiaohongshuSessionManager

manager = XiaohongshuSessionManager()
if not manager.ensure_login():
    manager.login_with_qr()  # 打开浏览器进行扫码登录

cookies = manager.get_cookies()
print("当前 Cookie 数量:", len(cookies))
```

导入 Cookie 文件：

```python
from pathlib import Path
from xiaohongshuagent import XiaohongshuSessionManager

manager = XiaohongshuSessionManager()
manager.login_with_cookie_file(Path("./exported_cookies.json"))
```

### 容错与日志

- 若本地没有 Cookie，会提示重新扫码或导入。
- 登录超时或 Playwright 组件出错时，会抛出 `LoginError` 并写入详细日志。
- 支持将日志写入自定义文件，便于接入后续的监控与报告模块。

### 测试方法

运行单元测试：

```bash
pytest
```

测试覆盖持久化与 Cookie 导入逻辑。Playwright 相关流程需在真实环境下手动验证。

## 模块 2：内容生成模块

`ContentGenerator` 负责调用大模型生成符合小红书风格的标题与正文，并驱动图片生成接口输出封面图，最终形成统一的「内容包」。

### 主要能力

- Prompt 模板内置小红书风格要素（口语化 + emoji + 话题标签）。
- 支持注入任意 GPT/Claude 文本客户端、DALL·E/Stable Diffusion 图片客户端。
- 自动解析模型返回的 JSON，规范化标签格式，生成本地图片文件。
- 失败时抛出 `ContentGenerationError` 并记录日志，方便重试或降级处理。

### 使用示例

```python
from xiaohongshuagent import ContentGenerator, OpenAITextClient, OpenAIImageClient

text_client = OpenAITextClient(model="gpt-4o-mini")
image_client = OpenAIImageClient(model="gpt-image-1")
generator = ContentGenerator(text_client=text_client, image_client=image_client)

package = generator.generate("春季护肤")
print(package.to_json())
```

离线测试或无 API Key 时，可自定义 Stub 客户端：

```python
from pathlib import Path
from xiaohongshuagent import ContentGenerator, PromptBuilder

class DummyTextClient:
    def generate_text(self, prompt: str) -> str:
        return '{"title": "示例标题", "body": "第一段\\n\\n第二段", "tags": ["#示例"]}'

class DummyImageClient:
    def generate_image(self, prompt: str, output_path: Path) -> Path:
        output_path.write_bytes(b"fake")
        return output_path

generator = ContentGenerator(
    text_client=DummyTextClient(),
    image_client=DummyImageClient(),
    prompt_builder=PromptBuilder(),
)
package = generator.generate("测试关键词")
print(package)
```

### 测试方法

运行所有单元测试（包含内容生成模块的桩实现）：

```bash
pytest
```

## 下一步计划

- 集成自动发帖流程，与登录/内容包联动。
- 扩展评论抓取与自动回复模块。
- 构建日志与日报输出能力。
