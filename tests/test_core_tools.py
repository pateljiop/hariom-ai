import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.browser import BrowserController
from app.computer import ComputerController
from app.workspace import Workspace
from app.terminal import run_command


class WorkspaceTests(unittest.TestCase):
    def test_write_read_and_list_stay_inside_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Workspace(root)
            written = ws.write_file("nested/demo.txt", "hello")
            self.assertEqual(written.read_text(encoding="utf-8"), "hello")
            self.assertEqual(ws.read_file("nested/demo.txt"), "hello")
            self.assertEqual([p.relative_to(ws.root).as_posix() for p in ws.list_files()], ["nested/demo.txt"])

    def test_path_escape_is_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Workspace(root)
            with self.assertRaises(ValueError):
                ws.read_file("../outside.txt")


class TerminalSafetyTests(unittest.TestCase):
    def test_risky_command_requires_approval(self):
        with self.assertRaises(PermissionError):
            run_command("git push --force", Mock())

    def test_approved_command_runs(self):
        activity = Mock()
        code, output = run_command("python -c \"print('ok')\"", activity, approved=True)
        self.assertEqual(code, 0)
        self.assertIn("ok", output)
        activity.emit.assert_any_call("TERMINAL -> exit code 0")


class BrowserValidationTests(unittest.TestCase):
    def setUp(self):
        self.controller = BrowserController(Mock())

    def test_http_and_https_urls_are_allowed(self):
        self.assertEqual(self.controller._validate_url("https://example.com"), "https://example.com")
        self.assertEqual(self.controller._validate_url("http://example.com/path"), "http://example.com/path")

    def test_non_http_urls_are_rejected(self):
        for url in ("file:///C:/secret.txt", "javascript:alert(1)", "example.com"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    self.controller._validate_url(url)


class ComputerSafetyTests(unittest.TestCase):
    @patch("app.computer.platform.system", return_value="Linux")
    def test_computer_control_is_windows_only(self, _system):
        controller = ComputerController(Mock())
        with self.assertRaisesRegex(RuntimeError, "Windows only"):
            controller.screen_size()


if __name__ == "__main__":
    unittest.main()
