from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
import os

from .config import APP_DIR


@dataclass
class BrowserSession:
    browser: object
    page: object


class BrowserController:
    """Optional Playwright browser controller for Hariom AI."""

    def __init__(self, activity, headless=True):
        self.activity = activity
        self.headless = headless
        self.session = None
        self._owner_thread_id = None
        self.browser_name = os.getenv("HARIOM_BROWSER", "brave").strip().lower() or "brave"

    def _reset_stale_session(self):
        import threading
        current = threading.get_ident()
        if self.session is not None and self._owner_thread_id not in (None, current):
            self.activity.emit("BROWSER -> resetting stale cross-thread session")
            try:
                self.session.browser.close()
            except Exception:
                pass
            try:
                self.session.playwright.stop()
            except Exception:
                pass
            self.session = None
            self._owner_thread_id = None

    def _playwright(self):
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Browser control needs Playwright. Install with "
                "'pip install playwright' and 'playwright install chromium'."
            ) from exc

    def _validate_url(self, url):
        parsed = urlparse(str(url))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Only valid http/https URLs are allowed.")
        return str(url)

    def _find_brave(self):
        candidates = [
            os.getenv("BRAVE_PATH", ""),
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return candidate
        return None

    def set_browser(self, browser):
        value = str(browser).strip().lower()
        if value not in {"brave", "chromium"}:
            raise ValueError("Browser must be 'brave' or 'chromium'.")
        if self.session:
            self.close()
        self.browser_name = value
        self.activity.emit("BROWSER -> selected " + value)
        return value

    def browser_status(self):
        executable = self._find_brave() if self.browser_name == "brave" else None
        return {"browser": self.browser_name, "available": bool(executable) if self.browser_name == "brave" else True, "executable": executable or ""}

    def _launch_browser(self, playwright):
        try:
            if self.browser_name == "brave":
                executable = self._find_brave()
                if not executable:
                    raise RuntimeError("Brave browser was selected but brave.exe was not found. Set BRAVE_PATH or install Brave Browser.")
                self.activity.emit("BROWSER -> launching Brave")
                return playwright.chromium.launch(headless=self.headless, executable_path=executable)
            self.activity.emit("BROWSER -> launching Playwright Chromium")
            return playwright.chromium.launch(headless=self.headless)
        except Exception as exc:
            message = str(exc)
            missing = "Executable doesn't exist" in message or "playwright install" in message
            if not missing or self.browser_name == "brave":
                raise
            self.activity.emit("BROWSER -> Chromium missing; installing Playwright Chromium")
            try:
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, timeout=180)
            except Exception as install_exc:
                raise RuntimeError("Playwright Chromium is missing and automatic installation failed: " + str(install_exc)) from install_exc
            self.activity.emit("BROWSER -> Chromium installed; retrying launch")
            return playwright.chromium.launch(headless=self.headless)

    def open(self, url):
        url = self._validate_url(url)
        self._reset_stale_session()
        if self.session is None:
            playwright = self._playwright()().start()
            try:
                browser = self._launch_browser(playwright)
            except Exception:
                playwright.stop()
                raise
            page = browser.new_page()
            self.session = BrowserSession(browser=browser, page=page)
            self.session.playwright = playwright
            import threading
            self._owner_thread_id = threading.get_ident()
        self.session.page.goto(url, wait_until="domcontentloaded")
        self.activity.emit("BROWSER -> opened " + url)
        return {"url": self.session.page.url, "title": self.session.page.title()}

    def current_page(self):
        self._reset_stale_session()
        if not self.session:
            raise RuntimeError("No browser session is open.")
        return {"url": self.session.page.url, "title": self.session.page.title()}

    def read_text(self, selector="body"):
        self._reset_stale_session()
        if not self.session:
            raise RuntimeError("No browser session is open.")
        text = self.session.page.locator(selector).inner_text(timeout=10000)
        return text[:12000]

    def click(self, selector):
        self._reset_stale_session()
        if not self.session:
            raise RuntimeError("No browser session is open.")
        self.session.page.locator(selector).first.click(timeout=10000)
        self.activity.emit("BROWSER -> clicked " + selector)
        return {"url": self.session.page.url, "title": self.session.page.title()}

    def type_text(self, selector, text):
        self._reset_stale_session()
        if not self.session:
            raise RuntimeError("No browser session is open.")
        self.session.page.locator(selector).first.fill(str(text), timeout=10000)
        self.activity.emit("BROWSER -> filled " + selector)
        return True

    def screenshot(self, path=None):
        self._reset_stale_session()
        if not self.session:
            raise RuntimeError("No browser session is open.")
        target = Path(path).expanduser().resolve() if path else (APP_DIR / "screenshots" / "browser.png").resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        self.session.page.screenshot(path=str(target), full_page=True)
        self.activity.emit("BROWSER -> screenshot " + str(target))
        return str(target)

    def close(self):
        if not self.session:
            return False
        try:
            self.session.browser.close()
            self.session.playwright.stop()
        finally:
            self.session = None
            self._owner_thread_id = None
        self.activity.emit("BROWSER -> closed")
        return True
