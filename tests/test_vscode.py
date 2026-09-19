import unittest

from app import vscode


class VSCodeContextTests(unittest.TestCase):
    def test_parse_title_extracts_active_file_and_project(self):
        parsed = vscode._parse_title("calculator.py - hariom-ai - Visual Studio Code")
        self.assertEqual(parsed, ("calculator.py", "hariom-ai"))

    def test_parse_title_ignores_welcome_screen(self):
        parsed = vscode._parse_title("Welcome - hariom-ai - Visual Studio Code")
        self.assertEqual(parsed, ("", "hariom-ai"))

    def test_context_shape_is_read_only(self):
        context = vscode.context(".")
        self.assertIn("windows", context)
        self.assertIn("running", context)
        self.assertIn("window_titles", context)
        self.assertIn("active_file", context)
        self.assertIn("active_project", context)
        self.assertIn("active_file_exists", context)
        self.assertIn("workspace_file", context)


if __name__ == "__main__":
    unittest.main()
