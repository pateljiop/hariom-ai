import subprocess
import tempfile
import unittest

from app.agent import Agent
from app.workspace import Workspace


class Activity:
    def __init__(self):
        self.events = []

    def emit(self, message):
        self.events.append(message)


class Approval:
    def __init__(self, allowed):
        self.allowed = allowed
        self.calls = []

    def __call__(self, action, detail):
        self.calls.append((action, detail))
        return self.allowed


class Router:
    def __init__(self):
        self.calls = 0

    def plan(self, prompt, system, preferred=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "steps": [
                    {"tool": "run_command", "args": {"command": "python -c \"raise SystemExit(1)\""}}
                ],
                "goal": "run a failing test",
            }, "fake"
        return {
            "steps": [
                {"tool": "write_file", "args": {"path": "recovered.txt", "content": "recovered"}}
            ],
            "goal": "recover",
        }, "fake"

    def chat(self, prompt, system="", preferred=None):
        return "verified summary", "fake"


class MalformedPlanRouter:
    def __init__(self):
        self.calls = 0

    def plan(self, prompt, system, preferred=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "steps": [{"tool": "write_file", "args": {"content": "calculator"}}],
                "goal": "create calculator",
            }, "fake"
        return {
            "steps": [
                {
                    "tool": "write_file",
                    "args": {
                        "path": "calculator.py",
                        "content": "print('calculator')",
                    },
                }
            ],
            "goal": "create calculator",
        }, "fake"

    def chat(self, prompt, system="", preferred=None):
        return "calculator created", "fake"


class AgentRecoveryTests(unittest.TestCase):
    def test_git_context_tools_are_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            activity = Activity()
            ws = Workspace(tmp)
            agent = Agent(Router(), ws, activity)
            result = agent._execute("git_branch", {})
            self.assertIn("exit_code", result)
            with self.assertRaises(PermissionError):
                agent._execute("git_commit", {"message": "test"})

            subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=tmp,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=tmp,
                check=True,
                capture_output=True,
            )
            (ws.root / "approval.txt").write_text("approved", encoding="utf-8")

            approval = Approval(True)
            agent = Agent(Router(), ws, activity, approval_callback=approval)
            result = agent._execute("git_commit", {"message": "test"})
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(approval.calls[0][0], "git_commit")

    def test_recovery_cycle_after_failed_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            activity = Activity()
            ws = Workspace(tmp)
            agent = Agent(Router(), ws, activity)
            summary, results = agent.run("complete recovery test")
            self.assertEqual(summary, "verified summary")
            self.assertTrue((ws.root / "recovered.txt").is_file())
            self.assertGreaterEqual(len(results), 2)
            self.assertTrue(any("recovering" in event for event in activity.events))

    def test_run_tests_tool_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            activity = Activity()
            ws = Workspace(tmp)
            agent = Agent(Router(), ws, activity)
            (ws.root / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertEqual(2 + 2, 4)\n",
                encoding="utf-8",
            )
            result = agent._execute("run_tests", {"command": "python -m unittest discover -v"})
            self.assertEqual(result["action"], "run_tests")
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("OK", result["output"])

    def test_failed_test_run_triggers_recovery(self):
        class TestRecoveryRouter:
            def __init__(self):
                self.calls = 0

            def plan(self, prompt, system, preferred=None):
                self.calls += 1
                if self.calls == 1:
                    return {"steps": [{"tool": "run_tests", "args": {"command": "python -c \\\"raise SystemExit(1)\\\""}}], "goal": "run tests"}, "fake"
                return {"steps": [{"tool": "write_file", "args": {"path": "fixed.txt", "content": "fixed"}}], "goal": "recover"}, "fake"

            def chat(self, prompt, system="", preferred=None):
                return "recovered after test failure", "fake"

        with tempfile.TemporaryDirectory() as tmp:
            activity = Activity()
            ws = Workspace(tmp)
            agent = Agent(TestRecoveryRouter(), ws, activity)
            summary, results = agent.run("fix the failing tests")
            self.assertEqual(summary, "recovered after test failure")
            self.assertTrue((ws.root / "fixed.txt").is_file())
            self.assertTrue(any(item.get("result", {}).get("action") == "run_tests" for item in results))
            self.assertTrue(any("recovering from cycle 1 failure" in event for event in activity.events))

    def test_malformed_tool_plan_is_replanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            activity = Activity()
            ws = Workspace(tmp)
            agent = Agent(MalformedPlanRouter(), ws, activity)
            summary, results = agent.run("ek python script likho calculator ke liye")
            self.assertEqual(summary, "calculator created")
            self.assertTrue((ws.root / "calculator.py").is_file())
            self.assertTrue(any("requires 'path'" in item.get("error", "") for item in results))
            self.assertTrue(any("recovering from cycle 1 failure" in event for event in activity.events))


if __name__ == "__main__":
    unittest.main()
