import unittest
from unittest.mock import Mock, patch

from app.terminal import run_command


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.activity = Mock()

    @patch("app.terminal.subprocess.run")
    def test_uses_argv_without_shell(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "ok"
        run.return_value.stderr = ""
        code, out = run_command("python --version", self.activity)
        self.assertEqual(code, 0)
        self.assertEqual(out, "ok")
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(run.call_args.args[0], ["python", "--version"])

    def test_shell_metacharacters_blocked(self):
        with self.assertRaises(PermissionError):
            run_command("python --version & whoami", self.activity)

    @patch("app.terminal.subprocess.run")
    def test_timeout_returns_124(self, run):
        import subprocess
        run.side_effect = subprocess.TimeoutExpired("python", 120, output="partial")
        code, out = run_command("python --version", self.activity)
        self.assertEqual(code, 124)
        self.assertIn("partial", out)

    def test_risky_command_requires_approval(self):
        with self.assertRaises(PermissionError):
            run_command("git reset --hard", self.activity)

if __name__ == "__main__":
    unittest.main()
