import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import gateway
from app.browser import BrowserController
from app.computer import ComputerController
from app.workspace import Workspace
from app.terminal import run_command
from app.activity import ActivityBus
from app.tool_registry import ToolRegistry, ToolError, UnknownToolError
from app.task_executor import TaskAction, TaskExecutor
from app.workspace_patcher import PatchError, TextPatch, WorkspacePatcher
from app.test_runner import TestRunner, TestRunnerError


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


class _Body:
    def __init__(self, data):
        import io
        self.rfile = io.BytesIO(data)
        self.headers = {"Content-Length": str(len(data))}


class GatewayRequestTests(unittest.TestCase):
    def _handler(self, body):
        handler = object.__new__(gateway.Handler)
        holder = _Body(body)
        handler.rfile = holder.rfile
        handler.headers = holder.headers
        return handler

    def test_gateway_rejects_invalid_json_as_client_error(self):
        handler = self._handler(b"{not-json")
        with self.assertRaises(gateway.ClientRequestError):
            handler._json_body()

    def test_gateway_accepts_valid_json(self):
        handler = self._handler(b'{"messages":[{"role":"user","content":"hi"}]}')
        self.assertEqual(handler._json_body()["messages"][0]["role"], "user")

    def test_gateway_rejects_oversized_body(self):
        handler = self._handler(b"{}")
        handler.headers["Content-Length"] = "5000001"
        with self.assertRaises(gateway.ClientRequestError):
            handler._json_body()


class StartupTests(unittest.TestCase):
    def test_main_delegates_to_ui_launcher(self):
        from app import main
        with patch.object(main, "launch") as launch:
            main.main()
            launch.assert_called_once_with()

    def test_activity_bus_notifies_subscribers(self):
        from app.activity import ActivityBus
        received = []
        bus = ActivityBus()
        bus.subscribe(received.append)
        bus.emit("startup")
        self.assertEqual(len(received), 1)
        self.assertIn("startup", received[0])


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        from app.activity import ActivityBus
        from app.tool_registry import ToolRegistry
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Workspace(self.temp.name)
        self.activity = ActivityBus()
        self.registry = ToolRegistry(self.workspace, self.activity)

    def tearDown(self):
        self.temp.cleanup()

    def test_describe_exposes_structured_tools(self):
        names = {item["name"] for item in self.registry.describe()}
        self.assertTrue({"workspace.list", "workspace.read", "workspace.write", "terminal.run"} <= names)

    def test_workspace_write_then_read(self):
        result = self.registry.execute("workspace.write", {"path": "agent.txt", "content": "hello"})
        self.assertTrue(result["ok"])
        result = self.registry.execute("workspace.read", {"path": "agent.txt"})
        self.assertEqual(result["result"], "hello")

    def test_unknown_tool_is_rejected(self):
        from app.tool_registry import UnknownToolError
        with self.assertRaises(UnknownToolError):
            self.registry.execute("does.not.exist")

    def test_non_object_arguments_are_rejected(self):
        from app.tool_registry import ToolError
        with self.assertRaises(ToolError):
            self.registry.execute("workspace.list", [])

    def test_terminal_uses_existing_approval_gate(self):
        blocked = self.registry.execute("terminal.run", {"command": "del dangerous.txt"})
        self.assertFalse(blocked["ok"])
        self.assertIn("approval", blocked["error"].lower())


class TaskExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Workspace(self.temp.name)
        self.activity = ActivityBus()
        self.registry = ToolRegistry(self.workspace, self.activity)
        self.executor = TaskExecutor(self.registry)

    def tearDown(self):
        self.temp.cleanup()

    def test_executes_multiple_actions_in_order(self):
        result = self.executor.execute([
            TaskAction("workspace.write", {"path": "task.txt", "content": "hello"}),
            TaskAction("workspace.read", {"path": "task.txt"}),
        ])
        self.assertTrue(result["ok"])
        self.assertEqual(result["results"][1]["result"], "hello")

    def test_failure_stops_execution_and_preserves_results(self):
        result = self.executor.execute([
            TaskAction("workspace.write", {"path": "task.txt", "content": "hello"}),
            TaskAction("workspace.read", {"path": "missing.txt"}),
            TaskAction("workspace.write", {"path": "after.txt", "content": "no"}),
        ])
        self.assertFalse(result["ok"])
        self.assertTrue(result["stopped"])
        self.assertEqual(result["index"], 1)
        self.assertEqual(len(result["results"]), 1)
        self.assertFalse((self.workspace.root / "after.txt").exists())

    def test_unknown_tool_is_rejected_before_execution(self):
        with self.assertRaises(UnknownToolError):
            self.executor.execute([TaskAction("missing.tool", {})])

    def test_risky_terminal_command_remains_approval_gated(self):
        result = self.executor.execute([TaskAction("terminal.run", {"command": "shutdown now"})])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "execution_error")
        self.assertIn("approval", result["error"].lower())

    def test_explicitly_approved_terminal_command_runs(self):
        result = self.executor.execute([TaskAction("terminal.run", {"command": "python -c \\\"print(42)\\\""}, approved=True)])
        self.assertTrue(result["ok"])


class WorkspacePatcherTests(unittest.TestCase):
    def test_exact_patch_applies_once(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Workspace(root)
            ws.write_file("demo.txt", "alpha beta alpha")
            patcher = WorkspacePatcher(ws)
            result = patcher.apply(TextPatch("demo.txt", "alpha beta", "gamma"))
            self.assertEqual(result["replacements"], 1)
            self.assertEqual(ws.read_file("demo.txt"), "gamma alpha")

    def test_patch_rejects_unexpected_match_count(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Workspace(root)
            ws.write_file("demo.txt", "alpha alpha")
            with self.assertRaises(PatchError):
                WorkspacePatcher(ws).apply(TextPatch("demo.txt", "alpha", "beta"))

    def test_patch_respects_workspace_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Workspace(root)
            with self.assertRaises(ValueError):
                WorkspacePatcher(ws).apply(TextPatch("../escape.txt", "x", "y"))


class TestRunnerTests(unittest.TestCase):
    def test_runner_reports_success(self):
        with tempfile.TemporaryDirectory() as root:
            result = TestRunner(root).run("tests")
            self.assertIn("ok", result)
            self.assertFalse(result["timed_out"])

    def test_runner_rejects_empty_target(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(TestRunnerError):
                TestRunner(root).run("")
