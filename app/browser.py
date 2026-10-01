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

    SENSITIVE_FIELD_TERMS = (
        "password", "passcode", "passwd", "secret", "token", "api_key",
        "apikey", "cvv", "cvc", "cardnumber", "card_number", "creditcard",
        "credit_card", "otp", "one-time-code", "securitycode",
    )
    SIDE_EFFECT_TERMS = (
        "submit", "send", "purchase", "buy", "pay", "checkout", "confirm",
        "delete", "remove", "publish", "post", "login", "sign-in", "signin",
        "logout", "authorize", "transfer", "withdraw",
    )

    def __init__(self, activity, headless=True, workspace=None, action_timeout_ms=15000):
        self.activity = activity
        self.headless = headless
        self.workspace = workspace
        self.action_timeout_ms = max(1000, int(action_timeout_ms))
        self.session = None
        self._temporary_artifacts = set()

    @classmethod
    def selector_is_sensitive(cls, selector):
        value = str(selector).lower()
        return any(term in value for term in cls.SENSITIVE_FIELD_TERMS)

    @classmethod
    def selector_has_side_effect(cls, selector):
        value = str(selector).lower()
        return any(term in value for term in cls.SIDE_EFFECT_TERMS)

    def _persistent_path(self, path):
        if self.workspace is None:
            raise PermissionError("Persistent browser artifacts require a workspace boundary.")
        return self.workspace._safe_path(path)

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

    @classmethod
    def _resolved_addresses(cls, hostname):
        try:
            infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise PermissionError("Browser destination hostname could not be safely resolved.") from exc
        addresses = {item[4][0] for item in infos}
        if not addresses or any(cls._host_is_private(address) for address in addresses):
            raise PermissionError("Browser destination resolves to a local/private network address.")
        return addresses

    def _validate_url(self, url):
        parsed = urlparse(str(url))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only valid http/https URLs are allowed.")
        if self._host_is_private(parsed.hostname):
            raise PermissionError("Browser navigation to local/private network destinations is blocked.")
        self._resolved_addresses(parsed.hostname)
        return str(url)

    def _route_is_safe(self, request_url):
        parsed = urlparse(str(request_url))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if self._host_is_private(parsed.hostname):
            return False
        try:
            self._resolved_addresses(parsed.hostname)
        except PermissionError:
            return False
        return True

    def _handle_route(self, route):
        if self._route_is_safe(route.request.url):
            route.continue_()
        else:
            route.abort("blockedbyclient")

    def open(self, url):
        url = self._validate_url(url)
        if self.session is None:
            playwright = self._playwright()().start()
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(service_workers="block")
            context.route("**/*", self._handle_route)
            page = context.new_page()
            self.session = BrowserSession(browser, page, playwright, context)
        self.session.page.goto(url, wait_until="domcontentloaded", timeout=self.action_timeout_ms)
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
            "text": page.locator(selector).inner_text(timeout=self.action_timeout_ms)[:12000],
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
            target = self._persistent_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            self.session.page.screenshot(path=str(target), full_page=True)
            self.activity.emit("BROWSER -> screenshot persisted")
            return str(target)
        with tempfile.NamedTemporaryFile(prefix="hariom-browser-", suffix=".png", delete=False) as tmp:
            target = Path(tmp.name)
        self.session.page.screenshot(path=str(target), full_page=True)
        self._temporary_artifacts.add(target)
        self.activity.emit("BROWSER -> screenshot temporary")
        return str(target)

    def cleanup_temp(self, path):
        target = Path(path).expanduser().resolve()
        if target not in self._temporary_artifacts:
            raise ValueError("Only tracked browser temporary artifacts can be cleaned up.")
        if target.exists():
            target.unlink()
        self._temporary_artifacts.discard(target)
        return True

    def close(self):
        if not self.session:
            return False
        try:
            self.session.browser.close()
        finally:
            self.session.playwright.stop()
            self.session = None
            for artifact in tuple(self._temporary_artifacts):
                try:
                    artifact.unlink(missing_ok=True)
                except OSError:
                    pass
            self._temporary_artifacts.clear()
        self.activity.emit("BROWSER -> closed")
        return True
