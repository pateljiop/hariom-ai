import unittest
from unittest.mock import Mock

from app.browser import BrowserController
from app.tools import ToolRegistry
from app.workspace import Workspace


class BrowserControllerTests(unittest.TestCase):
    def test_rejects_non_http_urls(self):
        browser = BrowserController(Mock())
        with self.assertRaises(ValueError):
            browser._validate_url("file:///tmp/test.html")

    def test_browser_tools_are_registered(self):
        with __import__("tempfile").TemporaryDirectory() as d:
            browser = BrowserController(Mock())
            registry = ToolRegistry(Workspace(d), Mock(), browser=browser)
            self.assertIn("browser_open", registry.names())
            self.assertIn("browser_read", registry.names())
            self.assertIn("browser_click", registry.names())


if __name__ == "__main__":
    unittest.main()
