from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse


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

    def _launch_browser(self, playwright):
        try:
            return playwright.chromium.launch(headless=self.headless)
        except Exception as exc:
            message = str(exc)
            missing = "Executable doesn't exist" in message or "playwright install" in message
            if not missing:
                raise
            self.activity.emit("BROWSER -> Chromium missing; installing Playwright Chromium")
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    check=True,
                    timeout=180,
                )
            except Exception as install_exc:
                raise RuntimeError(
                    "Playwright Chromium is missing and automatic installation failed: "
                    + str(install_exc)
                ) from install_exc
            self.activity.emit("BROWSER -> Chromium installed; retrying launch")
            return playwright.chromium.launch(headless=self.headless)

    def open(self, url):
        url = self._validate_url(url)
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
        self.session.page.goto(url, wait_until="domcontentloaded")
        self.activity.emit("BROWSER -> opened " + url)
        return {"url": self.session.page.url, "title": self.session.page.title()}

    def current_page(self):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        return {"url": self.session.page.url, "title": self.session.page.title()}

    def read_text(self, selector="body"):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        text = self.session.page.locator(selector).inner_text(timeout=10000)
        return text[:12000]

    def click(self, selector):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        self.session.page.locator(selector).first.click(timeout=10000)
        self.activity.emit("BROWSER -> clicked " + selector)
        return {"url": self.session.page.url, "title": self.session.page.title()}

    def type_text(self, selector, text):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        self.session.page.locator(selector).first.fill(str(text), timeout=10000)
        self.activity.emit("BROWSER -> filled " + selector)
        return True

    def screenshot(self, path="browser.png"):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        target = Path(path).expanduser().resolve()
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
        self.activity.emit("BROWSER -> closed")
        return True
