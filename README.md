# 小红书数字员工 MVP

该项目旨在构建一个可扩展的「小红书自媒体数字员工」原型，包含登录、内容生成、发帖、评论抓取、自动回复和日志报告等模块。当前实现专注于**模块 1：登录与会话管理**。

## 环境要求

- Python 3.9+
- [Playwright](https://playwright.dev/python/)

安装依赖：

```bash
pip install -r requirements.txt
playwright install chromium
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

---

后续模块将在此基础上逐步实现。
