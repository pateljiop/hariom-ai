from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class BrowserSession:
    browser: object
    page: object
    playwright: object


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

    def open(self, url):
        url = self._validate_url(url)
        if self.session is None:
            playwright = self._playwright()().start()
            browser = playwright.chromium.launch(headless=self.headless)
            page = browser.new_page()
            self.session = BrowserSession(browser, page, playwright)
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
        return self.session.page.locator(selector).inner_text(timeout=10000)[:12000]

    def click(self, selector, approved=False):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        if not approved:
            raise PermissionError("Browser click requires explicit approval.")
        self.session.page.locator(selector).first.click(timeout=10000)
        self.activity.emit("BROWSER -> clicked " + selector)
        return self.current_page()

    def type_text(self, selector, text, approved=False):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        if not approved:
            raise PermissionError("Browser typing requires explicit approval.")
        self.session.page.locator(selector).first.fill(str(text), timeout=10000)
        self.activity.emit("BROWSER -> filled " + selector)
        return True

    def screenshot(self, path="browser.png", approved=False):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        if not approved:
            raise PermissionError("Browser screenshot requires explicit approval.")
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
        finally:
            self.session.playwright.stop()
            self.session = None
        self.activity.emit("BROWSER -> closed")
        return True
