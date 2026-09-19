import unittest
import tempfile

from app.agent import Agent
from app.workspace import Workspace


class Activity:
    def __init__(self):
        self.events = []

    def emit(self, message):
        self.events.append(message)


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
