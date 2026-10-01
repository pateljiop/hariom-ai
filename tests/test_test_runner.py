import tempfile
import unittest
from unittest.mock import patch

from app.test_runner import TestRunner, TestRunnerError


class TestRunnerTests(unittest.TestCase):
    def test_accepts_workspace_scoped_unittest_discovery(self):
        with tempfile.TemporaryDirectory() as root:
            runner = TestRunner(root)
            with patch("app.test_runner.subprocess.run") as run:
                process = run.return_value
                process.returncode = 0
                process.stdout = "ok"
                process.stderr = ""
                result = runner.run_command("python -m unittest discover -s tests -v")
            self.assertTrue(result["ok"])
            args = run.call_args.args[0]
            self.assertEqual(args[:4], ["python", "-m", "unittest", "discover"])
            self.assertFalse(run.call_args.kwargs["shell"])

    def test_rejects_arbitrary_python_execution(self):
        runner = TestRunner(tempfile.mkdtemp())
        with self.assertRaises(TestRunnerError):
            runner.run_command('python -c "print(1)"')

    def test_rejects_non_python_commands(self):
        runner = TestRunner(tempfile.mkdtemp())
        with self.assertRaises(TestRunnerError):
            runner.run_command("git status")

    def test_rejects_discovery_path_escape(self):
        with tempfile.TemporaryDirectory() as root:
            runner = TestRunner(root)
            with self.assertRaises(TestRunnerError):
                runner.run_command("python -m unittest discover -s ../outside")

    def test_run_target_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as root:
            runner = TestRunner(root)
            with self.assertRaises(TestRunnerError):
                runner.run("../outside")


if __name__ == "__main__":
    unittest.main()
