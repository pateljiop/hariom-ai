import unittest

from app.browser import BrowserController


class BrowserUrlSecurityTests(unittest.TestCase):
    def setUp(self):
        self.controller = BrowserController(activity=None)

    def test_allows_public_http_and_https_hosts(self):
        self.assertEqual(self.controller._validate_url("https://example.com"), "https://example.com")
        self.assertEqual(self.controller._validate_url("http://example.com/path"), "http://example.com/path")

    def test_rejects_localhost_names(self):
        for url in (
            "http://localhost:8000",
            "https://localhost.localdomain",
            "http://service.localhost",
        ):
            with self.assertRaises(PermissionError):
                self.controller._validate_url(url)

    def test_rejects_private_and_local_ip_destinations(self):
        for host in ("127.0.0.1", "10.0.0.5", "172.16.0.10", "192.168.1.10", "::1", "169.254.169.254"):
            url = "http://" + ("[" + host + "]" if ":" in host else host)
            with self.assertRaises(PermissionError):
                self.controller._validate_url(url)

    def test_rejects_invalid_or_non_http_urls(self):
        for url in ("file:///etc/passwd", "ftp://example.com", "https://"):
            with self.assertRaises(ValueError):
                self.controller._validate_url(url)


if __name__ == "__main__":
    unittest.main()
