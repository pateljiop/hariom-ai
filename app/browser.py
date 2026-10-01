from dataclasses import dataclass
import ipaddress
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class BrowserSession:
    browser: object
    page: object
    playwright: object
    context: object = None


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
        if host == "localhost" or host.endswith(".localhost") or host == "localhost.localdomain":
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

    @classmethod
    def _resolve_public_host(cls, host):
        if cls._host_is_private(host):
            raise PermissionError("Browser navigation to local/private network destinations is blocked.")
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(f"Unable to resolve browser destination: {host}") from exc
        addresses = {info[4][0] for info in infos}
        if not addresses or any(cls._host_is_private(address) for address in addresses):
            raise PermissionError("Browser navigation to local/private network destinations is blocked.")

    def _validate_url(self, url):
        parsed = urlparse(str(url))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only valid http/https URLs are allowed.")
        self._resolve_public_host(parsed.hostname)
        return str(url)

    def _route_request(self, route):
        """Re-check every intercepted HTTP(S) request before it reaches the network."""
        url = route.request.url
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"}:
            try:
                self._resolve_public_host(parsed.hostname)
            except (PermissionError, ValueError):
                self.activity.emit("BROWSER -> blocked private/local network request")
                route.abort("blockedbyclient")
                return
        route.continue_()

    def open(self, url):
        url = self._validate_url(url)
        if self.session is None:
            playwright = self._playwright()().start()
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(service_workers="block")
            context.route("**/*", self._route_request)
            page = context.new_page()
            self.session = BrowserSession(browser, page, playwright, context)
        self.session.page.goto(url, wait_until="domcontentloaded")
        # Redirects can change the final destination; reject a private final URL
        # even though the initial destination was public.
        final_url = self.session.page.url
        self._validate_url(final_url)
        self.activity.emit("BROWSER -> opened " + final_url)
        return {"url": final_url, "title": self.session.page.title()}

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

    def find(self, selector, text=None):
        """Find matching elements and return bounded metadata without mutating the page."""
        if not self.session:
            raise RuntimeError("No browser session is open.")
        locator = self.session.page.locator(selector)
        count = locator.count()
        matches = []
        for index in range(min(count, 50)):
            item = locator.nth(index)
            item_text = item.inner_text(timeout=10000)[:1000]
            if text is not None and str(text) not in item_text:
                continue
            matches.append({
                "index": index,
                "text": item_text,
                "visible": item.is_visible(),
            })
        self.activity.emit("BROWSER -> found matching elements")
        return {"selector": selector, "count": len(matches), "matches": matches}

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
            if self.session.context is not None:
                self.session.context.close()
            else:
                self.session.browser.close()
        finally:
            self.session.playwright.stop()
            self.session = None
        self.activity.emit("BROWSER -> closed")
        return True
