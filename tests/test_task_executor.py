import unittest
from unittest.mock import Mock

from app.task_executor import TaskAction, TaskExecutor
from app.tool_registry import ToolApprovalRequired


class TaskExecutorStepStateTests(unittest.TestCase):
    def _executor(self, outcomes=None):
        registry = Mock()
        registry.describe.return_value = [{"name": "tool.a"}, {"name": "tool.b"}, {"name": "terminal.run"}]
        registry.workspace = Mock()
        registry.workspace.read_file.return_value = "present"
        registry.workspace.exists.return_value = True
        registry.test_runner = Mock()
        registry.test_runner.run_command.return_value = {"ok": True, "returncode": 0, "output": ""}
        registry.execute.side_effect = outcomes or [
            {"ok": True, "value": "a"},
            {"ok": True, "value": "b"},
        ]
        return TaskExecutor(registry), registry

    def test_tracks_each_step_and_checkpoints(self):
        executor, registry = self._executor()
        state = {}
        checkpoints = []
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a"), TaskAction("tool.b", {}, step_id="b", dependencies=("a",))],
            step_state=state,
            checkpoint=lambda: checkpoints.append({k: dict(v) for k, v in state.items()}),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(state["a"]["status"], "succeeded")
        self.assertEqual(state["b"]["status"], "succeeded")
        self.assertEqual(state["a"]["attempts"], 1)
        self.assertEqual(registry.execute.call_count, 2)
        self.assertGreaterEqual(len(checkpoints), 4)

    def test_restart_resume_does_not_rerun_succeeded_step(self):
        executor, registry = self._executor()
        state = {"a": {"step_id": "a", "status": "succeeded", "attempts": 1, "result": {"ok": True}, "error": None}}
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a"), TaskAction("tool.b", {}, step_id="b")],
            step_state=state,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(registry.execute.call_count, 1)
        registry.execute.assert_called_once_with("tool.b", {}, approved=False)

    def test_failed_dependency_is_skipped_on_resume(self):
        executor, registry = self._executor(outcomes=[{"ok": False, "error": "boom"}])
        state = {}
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a"), TaskAction("tool.b", {}, step_id="b", dependencies=("a",))],
            step_state=state,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(state["a"]["status"], "failed")
        self.assertEqual(state["b"]["status"], "skipped")

    def test_interrupted_step_requires_explicit_resume(self):
        executor, registry = self._executor()
        state = {'a': {'step_id': 'a', 'status': 'interrupted', 'attempts': 1, 'result': None, 'error': 'interrupted_by_restart'}}
        result = executor.execute([TaskAction('tool.a', {}, step_id='a')], step_state=state)
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_type'], 'recovery_required')
        registry.execute.assert_not_called()
        result = executor.execute([TaskAction('tool.a', {}, step_id='a')], step_state=state, resume_interrupted=True)
        self.assertTrue(result['ok'])
        self.assertEqual(state['a']['status'], 'succeeded')

    def test_retryable_step_retries_with_bounded_budget(self):
        executor, registry = self._executor(outcomes=[{"ok": False, "error": "temporary"}, {"ok": True, "value": "ok"}])
        state = {}
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a", retryable=True)],
            step_state=state,
            max_step_retries=1,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(state["a"]["status"], "succeeded")
        self.assertEqual(state["a"]["attempts"], 2)
        self.assertEqual(registry.execute.call_count, 2)

    def test_non_retryable_step_never_repeats(self):
        executor, registry = self._executor(outcomes=[{"ok": False, "error": "temporary"}, {"ok": True}])
        state = {}
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a")],
            step_state=state,
            max_step_retries=3,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(state["a"]["attempts"], 1)
        self.assertEqual(registry.execute.call_count, 1)

    def test_expected_file_is_verified_before_step_succeeds(self):
        executor, registry = self._executor()
        state = {}
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a", expected_files=("output.txt",))],
            step_state=state,
        )
        self.assertTrue(result["ok"])
        registry.workspace.exists.assert_called_once_with("output.txt")
        self.assertEqual(state["a"]["status"], "succeeded")

    def test_missing_expected_file_fails_step(self):
        executor, registry = self._executor()
        registry.workspace.exists.return_value = False
        state = {}
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a", expected_files=("output.txt",))],
            step_state=state,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "verification_error")
        self.assertEqual(state["a"]["status"], "failed")

    def test_step_test_command_is_verified(self):
        executor, registry = self._executor()
        registry.execute.side_effect = [{"ok": True, "value": "a"}]
        state = {}
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a", test_commands=("python -m unittest discover -s tests",), approved=True)],
            step_state=state,
        )
        self.assertTrue(result["ok"])
        registry.test_runner.run_command.assert_called_once_with("python -m unittest discover -s tests")
        registry.execute.assert_called_once_with("tool.a", {}, approved=True)

    def test_unsafe_test_command_fails_closed(self):
        executor, registry = self._executor()
        registry.test_runner.run_command.side_effect = ValueError("unsupported command")
        state = {}
        result = executor.execute(
            [TaskAction("tool.a", {}, step_id="a", test_commands=("python -c \"print(1)\"",))],
            step_state=state,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "verification_error")
        self.assertEqual(state["a"]["status"], "failed")

    def test_approval_required_returns_current_step_to_pending(self):
        executor, registry = self._executor()
        registry.execute.side_effect = ToolApprovalRequired("approval needed")
        state = {}
        result = executor.execute([TaskAction("tool.a", {}, step_id="a")], step_state=state)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "approval_required")
        self.assertEqual(state["a"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
