import unittest
from unittest.mock import Mock

from app.task_executor import TaskAction, TaskExecutor
from app.tool_registry import ToolApprovalRequired


class TaskExecutorStepStateTests(unittest.TestCase):
    def _executor(self, outcomes=None):
        registry = Mock()
        registry.describe.return_value = [{"name": "tool.a"}, {"name": "tool.b"}]
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
        resumed = executor.execute(
            [TaskAction("tool.a", {}, step_id="a"), TaskAction("tool.b", {}, step_id="b", dependencies=("a",))],
            step_state=state,
        )
        self.assertFalse(resumed["ok"])
        self.assertEqual(state["b"]["status"], "skipped")

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
