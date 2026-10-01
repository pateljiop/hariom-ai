import unittest
from unittest.mock import patch

from app.browser import BrowserController


class BrowserUrlSecurityCurrentTests(unittest.TestCase):
    def setUp(self):
        self.controller = BrowserController(activity=None)

    def test_public_http_https_host_is_allowed(self):
        with patch("app.browser.socket.getaddrinfo", return_value=[(2, 0, 0, "", ("93.184.216.34", 0))]):
            self.assertEqual(self.controller._validate_url("https://example.com"), "https://example.com")
            self.assertEqual(self.controller._validate_url("http://example.com/path"), "http://example.com/path")

    def test_private_literal_hosts_are_rejected(self):
        for host in ("localhost", "127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1"):
            url = "http://[" + host + "]" if ":" in host else "http://" + host
            with self.assertRaises(PermissionError):
                self.controller._validate_url(url)

    def test_public_hostname_resolving_to_private_address_is_rejected(self):
        with patch("app.browser.socket.getaddrinfo", return_value=[(2, 0, 0, "", ("192.168.1.10", 0))]):
            with self.assertRaises(PermissionError):
                self.controller._validate_url("https://example.com")

    def test_invalid_scheme_is_rejected(self):
        with self.assertRaises(ValueError):
            self.controller._validate_url("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()
