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

    def test_project_context_tool_is_read_only_and_structured(self):
        with tempfile.TemporaryDirectory() as tmp:
            activity = Activity()
            ws = Workspace(tmp)
            (ws.root / "requirements.txt").write_text("requests\n", encoding="utf-8")
            (ws.root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            agent = Agent(Router(), ws, activity)

            result = agent._execute("project_context", {})

            self.assertEqual(result["workspace"], str(ws.root))
            self.assertEqual(result["file_count"], 2)
            self.assertIn("requirements.txt", result["manifests"])
            self.assertEqual(result["extensions"][".py"], 1)
            self.assertEqual(result["extensions"][".txt"], 1)
            self.assertIn("windows", result)
            self.assertIn("vscode_running", result)
            self.assertIn("git_branch", result)
            self.assertIn("git_status", result)

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
                    return {"steps": [{"tool": "run_tests", "args": {"command": "python -c \"raise SystemExit(1)\""}}], "goal": "run tests"}, "fake"
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


    def test_github_request_cannot_complete_without_github_evidence(self):
        class IncompleteGitHubRouter:
            def plan(self, prompt, system, preferred=None):
                return {
                    "steps": [{"tool": "list_workspace", "args": {}}],
                    "goal": "inspect workspace",
                }, "fake"

            def chat(self, prompt, system="", preferred=None):
                return "incomplete", "fake"

        with tempfile.TemporaryDirectory() as tmp:
            activity = Activity()
            ws = Workspace(tmp)
            agent = Agent(IncompleteGitHubRouter(), ws, activity)
            summary, _ = agent.run("Check the GitHub repository and tell me the open issues.")
            self.assertEqual(summary, "incomplete")
            self.assertTrue(any("task ended with failures" in event for event in activity.events))

    def test_github_limit_string_is_normalized(self):
        activity = Activity()
        with tempfile.TemporaryDirectory() as tmp:
            agent = Agent(Router(), Workspace(tmp), activity)
            args = {"limit": "20"}
            agent._normalize_args("github_branches", args)
            self.assertEqual(args["limit"], 20)
            self.assertIsNone(agent._validate_step("github_branches", args))

    def test_read_file_blocks_git_internal_paths(self):
        activity = Activity()
        with tempfile.TemporaryDirectory() as tmp:
            agent = Agent(Router(), Workspace(tmp), activity)
            error = agent._validate_step("read_file", {"path": ".git/config"})
            self.assertIn("cannot inspect .git internal files", error)

    def test_set_workspace_rebinds_github_client(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            activity = Activity()
            agent = Agent(Router(), Workspace(first), activity)
            agent.set_workspace(Workspace(second))
            self.assertEqual(agent.workspace.root, Workspace(second).root)
            self.assertEqual(agent.github.root, Workspace(second).root)


if __name__ == "__main__":
    unittest.main()
