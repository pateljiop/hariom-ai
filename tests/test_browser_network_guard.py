import unittest
from unittest.mock import Mock, patch

from app.browser import BrowserController


class FakeRoute:
    def __init__(self, url):
        self.request = Mock(url=url)
        self.aborted = None
        self.continued = False

    def abort(self, error_code=None):
        self.aborted = error_code

    def continue_(self):
        self.continued = True


class BrowserNetworkGuardTests(unittest.TestCase):
    def test_route_blocks_private_request(self):
        browser = BrowserController(Mock())
        route = FakeRoute("http://127.0.0.1:8080/internal")
        with patch.object(browser, "_resolve_public_host", side_effect=PermissionError("blocked")):
            browser._route_request(route)
        self.assertEqual(route.aborted, "blockedbyclient")
        self.assertFalse(route.continued)

    def test_route_allows_public_request(self):
        browser = BrowserController(Mock())
        route = FakeRoute("https://example.com/")
        with patch.object(browser, "_resolve_public_host"):
            browser._route_request(route)
        self.assertIsNone(route.aborted)
        self.assertTrue(route.continued)

    def test_browser_session_keeps_context_optional(self):
        from app.browser import BrowserSession
        session = BrowserSession(object(), object(), object())
        self.assertIsNone(session.context)


if __name__ == "__main__":
    unittest.main()
