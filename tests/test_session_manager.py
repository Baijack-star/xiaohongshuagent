import json
from pathlib import Path

from xiaohongshuagent.session_manager import SessionConfig, XiaohongshuSessionManager


def test_storage_roundtrip(tmp_path: Path) -> None:
    config = SessionConfig(storage_dir=tmp_path, storage_filename="session.json")
    manager = XiaohongshuSessionManager(config=config)

    cookies = [
        {
            "name": "xhs_spses",
            "value": "fake-session",
            "domain": ".xiaohongshu.com",
            "path": "/",
        }
    ]

    manager.save_cookies(cookies)
    stored = manager.get_cookies()
    assert stored == cookies

    # Ensure timestamp is written
    with (tmp_path / "session.json").open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    assert payload["cookies"] == cookies
    assert isinstance(payload["timestamp"], int)


def test_ensure_login(tmp_path: Path) -> None:
    manager = XiaohongshuSessionManager(
        config=SessionConfig(storage_dir=tmp_path, storage_filename="session.json")
    )
    assert manager.ensure_login() is False

    manager.save_cookies([
        {"name": "foo", "value": "bar", "domain": "example.com", "path": "/"}
    ])
    assert manager.ensure_login() is True


def test_cookie_file_import(tmp_path: Path) -> None:
    cookie_path = tmp_path / "cookies.json"
    cookies = {
        "cookies": [
            {"name": "token", "value": "123", "domain": "example.com", "path": "/"}
        ]
    }
    with cookie_path.open("w", encoding="utf-8") as fh:
        json.dump(cookies, fh)

    manager = XiaohongshuSessionManager(
        config=SessionConfig(storage_dir=tmp_path, storage_filename="session.json")
    )
    manager.login_with_cookie_file(cookie_path)
    assert manager.get_cookies() == cookies["cookies"]
