from dataclasses import dataclass
import ipaddress
import tempfile
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

    @staticmethod
    def _host_is_private(host):
        host = str(host).strip().lower().rstrip(".")
        if not host:
            return True
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
            return True
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any((
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_unspecified,
            address.is_reserved,
        ))

    def _validate_url(self, url):
        parsed = urlparse(str(url))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only valid http/https URLs are allowed.")
        if self._host_is_private(parsed.hostname):
            raise PermissionError("Browser navigation to local/private network destinations is blocked.")
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

    def observe(self, selector="body"):
        """Return fresh browser state for closed-loop agent decisions."""
        if not self.session:
            raise RuntimeError("No browser session is open.")
        page = self.session.page
        observation = {
            "url": page.url,
            "title": page.title(),
            "text": page.locator(selector).inner_text(timeout=10000)[:12000],
        }
        self.activity.emit("BROWSER -> observed current page")
        return observation

    def verify(self, selector=None, text=None, url_contains=None):
        """Check current browser state against explicit, user/task-provided expectations."""
        if not self.session:
            raise RuntimeError("No browser session is open.")
        page = self.session.page
        checks = []
        if selector:
            checks.append(("selector", bool(page.locator(selector).count())))
        if text is not None:
            checks.append(("text", str(text) in page.locator("body").inner_text(timeout=10000)))
        if url_contains is not None:
            checks.append(("url", str(url_contains) in page.url))
        if not checks:
            raise ValueError("At least one verification condition is required.")
        return {
            "ok": all(value for _, value in checks),
            "checks": [{"type": kind, "ok": value} for kind, value in checks],
            "url": page.url,
            "title": page.title(),
        }

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

    def type_text(self, selector, text, approved=False, sensitive=False):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        if not approved:
            raise PermissionError("Browser typing requires explicit approval.")
        self.session.page.locator(selector).first.fill(str(text), timeout=10000)
        self.activity.emit("BROWSER -> filled field" + (" [sensitive]" if sensitive else ""))
        return True

    def screenshot(self, path=None, approved=False, persist=False):
        if not self.session:
            raise RuntimeError("No browser session is open.")
        if not approved:
            raise PermissionError("Browser screenshot requires explicit approval.")
        if persist:
            if not path:
                raise ValueError("A path is required when persist=True.")
            target = Path(path).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            self.session.page.screenshot(path=str(target), full_page=True)
            self.activity.emit("BROWSER -> screenshot persisted")
            return str(target)
        with tempfile.NamedTemporaryFile(prefix="hariom-browser-", suffix=".png", delete=False) as tmp:
            target = Path(tmp.name)
        self.session.page.screenshot(path=str(target), full_page=True)
        self.activity.emit("BROWSER -> screenshot temporary")
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
