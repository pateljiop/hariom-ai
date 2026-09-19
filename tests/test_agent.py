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


if __name__ == "__main__":
    unittest.main()
