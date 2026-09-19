import unittest

from app.terminal import run_command


class Activity:
    def __init__(self):
        self.events = []

    def emit(self, message):
        self.events.append(message)


class TerminalSafetyTests(unittest.TestCase):
    def test_risky_command_is_blocked_without_approval(self):
        with self.assertRaises(PermissionError):
            run_command("del test.txt", Activity())

    def test_safe_command_runs(self):
        code, output = run_command("echo Hariom AI", Activity())
        self.assertEqual(code, 0)
        self.assertIn("Hariom AI", output)


if __name__ == "__main__":
    unittest.main()
