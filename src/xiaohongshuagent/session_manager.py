"""Login and session management for Xiaohongshu automation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .logging_utils import configure_logger

try:
    from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
except Exception:  # pragma: no cover - optional dependency for unit tests
    Browser = BrowserContext = Page = object  # type: ignore
    PlaywrightTimeoutError = Exception  # type: ignore
    sync_playwright = None  # type: ignore


class LoginError(RuntimeError):
    """Raised when login to Xiaohongshu fails."""


@dataclass
class SessionConfig:
    """Configuration for :class:`XiaohongshuSessionManager`."""

    storage_dir: Path = Path("data")
    storage_filename: str = "xiaohongshu_session.json"
    login_url: str = "https://creator.xiaohongshu.com/fe/api/login/qr"
    success_selector: str = "a[href*='creator']"
    headless: bool = False
    context_timeout: int = 30
    qr_timeout: int = 180

    def storage_path(self) -> Path:
        return self.storage_dir / self.storage_filename


class XiaohongshuSessionManager:
    """Manage Xiaohongshu login sessions via Playwright."""

    def __init__(
        self,
        config: Optional[SessionConfig] = None,
        *,
        logger_name: str = "xiaohongshu.session",
        log_file: Optional[Path] = None,
    ) -> None:
        self.config = config or SessionConfig()
        self.config.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = configure_logger(logger_name, log_file=log_file)

    # ------------------------------------------------------------------
    # Session persistence helpers
    # ------------------------------------------------------------------
    def _read_storage(self) -> Dict[str, Any]:
        storage_path = self.config.storage_path()
        if not storage_path.exists():
            return {"cookies": [], "timestamp": None}
        try:
            with storage_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                if "cookies" not in data:
                    data["cookies"] = []
                return data
        except json.JSONDecodeError as exc:
            self.logger.error("Failed to decode session file %s: %s", storage_path, exc)
            return {"cookies": [], "timestamp": None}

    def _write_storage(self, cookies: Iterable[Dict[str, Any]]) -> None:
        storage_path = self.config.storage_path()
        payload = {"cookies": list(cookies), "timestamp": int(time.time())}
        with storage_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        self.logger.info("Session cookies persisted to %s", storage_path)

    def get_cookies(self) -> List[Dict[str, Any]]:
        """Return cookies stored on disk."""

        data = self._read_storage()
        return list(data.get("cookies", []))

    def save_cookies(self, cookies: Iterable[Dict[str, Any]]) -> None:
        """Persist cookies to disk."""

        self._write_storage(cookies)

    # ------------------------------------------------------------------
    # Login flows
    # ------------------------------------------------------------------
    def login_with_qr(self) -> Dict[str, Any]:
        """Launch a browser window for QR-code login.

        The user must scan the QR code with the Xiaohongshu app.
        Once the success selector is detected the resulting cookies are saved.

        Returns
        -------
        dict
            Information about the login session including cookies and timestamp.

        Raises
        ------
        LoginError
            If login fails or Playwright is unavailable.
        """

        if sync_playwright is None:
            raise LoginError("Playwright is not installed. Install playwright to enable QR login.")

        self.logger.info("Starting QR login flow. Headless mode: %s", self.config.headless)

        try:
            with sync_playwright() as p:
                browser: Browser = p.chromium.launch(headless=self.config.headless)
                context: BrowserContext = browser.new_context()
                page: Page = context.new_page()
                page.goto(self.config.login_url, wait_until="networkidle")
                self.logger.info("Login page opened. Waiting for QR scan…")

                try:
                    page.wait_for_selector(
                        self.config.success_selector,
                        timeout=self.config.qr_timeout * 1000,
                    )
                except PlaywrightTimeoutError as exc:  # pragma: no cover - requires live login
                    self.logger.error("Timed out waiting for login confirmation: %s", exc)
                    raise LoginError("Login timed out. Please rescan the QR code.") from exc

                storage = context.storage_state()
                self.save_cookies(storage.get("cookies", []))
                self.logger.info("Login successful. Session saved.")
                return storage
        except LoginError:
            raise
        except Exception as exc:  # pragma: no cover - network interaction
            self.logger.exception("Unexpected error during QR login: %s", exc)
            raise LoginError(str(exc)) from exc
        finally:
            self.logger.debug("QR login flow finished.")

    def login_with_cookies(self, cookies: Iterable[Dict[str, Any]]) -> None:
        """Save imported cookies.

        The cookies must follow the structure expected by Playwright.
        """

        cookies = list(cookies)
        if not cookies:
            self.logger.warning("No cookies provided for import; skipping save.")
            return
        self.save_cookies(cookies)
        self.logger.info("Imported %d cookies from external source.", len(cookies))

    def login_with_cookie_file(self, cookie_file: Path) -> None:
        """Load cookies from an exported JSON file and persist them locally."""

        cookie_file = Path(cookie_file)
        if not cookie_file.exists():
            raise FileNotFoundError(f"Cookie file not found: {cookie_file}")
        with cookie_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        cookies = data.get("cookies", data)
        self.login_with_cookies(cookies)

    # ------------------------------------------------------------------
    # Session usage helpers
    # ------------------------------------------------------------------
    def ensure_login(self) -> bool:
        """Return ``True`` if cookies are available, otherwise ``False``."""

        cookies = self.get_cookies()
        if cookies:
            self.logger.debug("Loaded %d cookies from local storage.", len(cookies))
            return True
        self.logger.warning("No stored cookies found. Please login via QR or import cookies.")
        return False

    def create_authenticated_context(self, context: BrowserContext) -> None:
        """Apply stored cookies to an existing Playwright context."""

        cookies = self.get_cookies()
        if not cookies:
            raise LoginError("No cookies available. Please login first.")
        context.add_cookies(cookies)
        self.logger.info("Injected %d cookies into Playwright context.", len(cookies))

    def verify_login_status(
        self,
        page: Page,
        *,
        verification_selector: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> bool:
        """Verify that a user is logged in.

        Parameters
        ----------
        page:
            Playwright page instance.
        verification_selector:
            Selector that is visible only when logged in. If omitted the
            ``success_selector`` from :class:`SessionConfig` is used.
        timeout:
            Timeout in seconds. Defaults to :attr:`SessionConfig.context_timeout`.
        """

        selector = verification_selector or self.config.success_selector
        timeout_ms = (timeout or self.config.context_timeout) * 1000
        try:
            page.wait_for_selector(selector, timeout=timeout_ms)
            self.logger.info("Login status verified using selector %s", selector)
            return True
        except PlaywrightTimeoutError:  # pragma: no cover - requires playwright
            self.logger.warning("Failed to verify login status using selector %s", selector)
            return False


__all__ = [
    "XiaohongshuSessionManager",
    "SessionConfig",
    "LoginError",
]
