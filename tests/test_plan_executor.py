import unittest
from unittest.mock import Mock

from app.plan_executor import PlanExecutor, PlanExecutionError
from app.task_executor import TaskAction\nfrom app.task_service import TaskService\nfrom app.task_store import TaskStore


class PlanExecutorTests(unittest.TestCase):
    def test_prepare_converts_plan_and_returns_review_payload(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": True, "stage": "approval", "request_id": "abc", "diff": "d"}
        executor = PlanExecutor(workflow)

        result = executor.prepare({
            "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
            "test_target": "tests",
        })

        workflow.prepare.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual(result["request_id"], "abc")
        self.assertEqual(result["plan"]["test_target"], "tests")
        self.assertEqual([e["stage"] for e in result["state"]["events"]], ["validated", "executing", "approval"])

    def test_prepare_persists_task_lifecycle(self):\n        workflow = Mock()\n        workflow.prepare.return_value = {"ok": True, "stage": "approval", "request_id": "persisted"}\n        import tempfile\n        with tempfile.TemporaryDirectory() as root:\n            service = TaskService(TaskStore(f"{root}/tasks.sqlite3"))\n            executor = PlanExecutor(workflow, task_service=service)\n            result = executor.prepare({\n                "task_id": "task-persist",\n                "user_request": "write file",\n                "objective": "create file",\n                "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],\n            })\n            restored = service.get_task("task-persist")\n            self.assertEqual(restored.status.value, "awaiting_approval")\n            self.assertTrue(any(e["status"] == "awaiting_approval" for e in service.events("task-persist")))\n            self.assertEqual(result["request_id"], "persisted")\n\n    def test_prepare_failure_exposes_failed_state(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": False, "stage": "verification"}
        executor = PlanExecutor(workflow)

        result = executor.prepare({
            "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
        })

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"]["stage"], "failed")

    def test_prepare_rejects_malformed_external_plan(self):
        executor = PlanExecutor(Mock())
        with self.assertRaises(Exception):
            executor.prepare({"actions": []})

    def test_recover_repairs_and_reverifies_with_bounded_attempts(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": False, "stage": "verification"}
        test_runner = Mock()
        test_runner.run.side_effect = [{"ok": False}, {"ok": True}]
        workflow.executor.registry.test_runner = test_runner
        workflow.executor.execute.return_value = {"ok": True, "results": []}
        executor = PlanExecutor(workflow)

        prepared = executor.prepare({
            "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
        })
        task_id = prepared["state"]["task_id"]

        result = executor.recover(
            task_id,
            [TaskAction("workspace.write", {"path": "fix", "content": "ok"})],
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"], 1)
        workflow.executor.execute.assert_called_once()
        self.assertEqual(result["state"]["attempts"], 1)
        self.assertEqual(result["state"]["stage"], "approval")

    def test_recover_rejects_unknown_task(self):
        executor = PlanExecutor(Mock())
        with self.assertRaises(PlanExecutionError):
            executor.recover("missing", [TaskAction("workspace.write", {"path": "a", "content": "b"})])

    def test_approve_updates_matching_task_state(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": True, "stage": "approval", "request_id": "abc", "diff": "d"}
        workflow.approve.return_value = {"ok": True, "request_id": "abc", "commit": {"ok": True}}
        executor = PlanExecutor(workflow)
        prepared = executor.prepare({
            "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
        })

        result = executor.approve("abc", "reviewed change")

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["stage"], "committed")
        self.assertEqual(prepared["state"]["stage"], "approval")

    def test_get_state_unknown_task_raises(self):
        executor = PlanExecutor(Mock())
        with self.assertRaises(PlanExecutionError):
            executor.get_state("missing")


if __name__ == "__main__":
    unittest.main()
