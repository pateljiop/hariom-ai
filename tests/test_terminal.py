import unittest
from unittest.mock import Mock, patch

from app.terminal import run_command


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.activity = Mock()

    @patch("app.terminal.subprocess.Popen")
    def test_uses_argv_without_shell(self, popen):
        process = Mock()
        process.communicate.return_value = ("ok", "")
        process.returncode = 0
        popen.return_value = process

        code, out = run_command("python --version", self.activity)
        self.assertEqual(code, 0)
        self.assertEqual(out, "ok")
        self.assertFalse(popen.call_args.kwargs["shell"])
        self.assertEqual(popen.call_args.args[0], ["python", "--version"])

    def test_shell_metacharacters_blocked(self):
        with self.assertRaises(PermissionError):
            run_command("python --version & whoami", self.activity)

    @patch("app.terminal._terminate_process_tree")
    @patch("app.terminal.subprocess.Popen")
    def test_timeout_returns_124(self, popen, terminate):
        import subprocess
        process = Mock()
        process.pid = 12345
        process.communicate.side_effect = [
            subprocess.TimeoutExpired("python", 120, output="partial"),
            ("partial", ""),
        ]
        popen.return_value = process

        code, out = run_command("python --version", self.activity)
        self.assertEqual(code, 124)
        self.assertIn("partial", out)
        terminate.assert_called_once_with(process)

    def test_risky_command_requires_approval(self):
        with self.assertRaises(PermissionError):
            run_command("git reset --hard", self.activity)


if __name__ == "__main__":
    unittest.main()
