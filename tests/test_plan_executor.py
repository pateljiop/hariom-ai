import unittest
from unittest.mock import Mock

from app.plan_executor import PlanExecutor, PlanExecutionError
from app.task_executor import TaskAction, TaskExecutor
from app.task_service import TaskService
from app.task_store import TaskStore


class PlanExecutorTests(unittest.TestCase):
    def test_dependency_order_is_deterministic(self):
        executor = TaskExecutor(Mock())
        actions = [
            TaskAction("tool.c", {}, step_id="c", dependencies=("b",)),
            TaskAction("tool.a", {}, step_id="a"),
            TaskAction("tool.b", {}, step_id="b", dependencies=("a",)),
        ]
        ordered = executor._dependency_order(actions)
        self.assertEqual([a.step_id for a in ordered], ["a", "b", "c"])

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

    def test_prepare_persists_task_lifecycle(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": True, "stage": "approval", "request_id": "persisted"}
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            service = TaskService(TaskStore(f"{root}/tasks.sqlite3"))
            executor = PlanExecutor(workflow, task_service=service)
            result = executor.prepare({
                "task_id": "task-persist",
                "user_request": "write file",
                "objective": "create file",
                "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
            })
            restored = service.get_task("task-persist")
            self.assertEqual(restored.status.value, "awaiting_commit_approval")
            self.assertTrue(any(e["status"] == "awaiting_commit_approval" for e in service.events("task-persist")))
            self.assertEqual(result["request_id"], "persisted")

    def test_prepare_failure_exposes_failed_state(self):
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
        self.assertEqual(workflow.executor.execute.call_args.kwargs["task_id"], task_id)

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

    def test_get_state_restores_persisted_execution_state_after_restart(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": True, "stage": "approval", "request_id": "restart-approval", "diff": "d"}
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            service = TaskService(store)
            first = PlanExecutor(workflow, task_service=service)
            prepared = first.prepare({
                "task_id": "restart-task",
                "user_request": "restart recovery",
                "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
            })
            second = PlanExecutor(workflow, task_service=TaskService(TaskStore(f"{root}/tasks.sqlite3")))
            restored = second.get_state("restart-task")
            self.assertEqual(restored["task_id"], "restart-task")
            self.assertEqual(restored["stage"], "approval")
            self.assertEqual(restored["result"]["request_id"], "restart-approval")
            self.assertEqual(restored["events"][-1]["stage"], "approval")

    def test_recover_uses_persisted_state_after_restart(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": False, "stage": "verification"}
        test_runner = Mock()
        test_runner.run.side_effect = [{"ok": False}, {"ok": True}]
        workflow.executor.registry.test_runner = test_runner
        workflow.executor.execute.return_value = {"ok": True, "results": []}
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            first = PlanExecutor(workflow, task_service=TaskService(store))
            prepared = first.prepare({
                "task_id": "recover-restart",
                "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
            })
            second = PlanExecutor(workflow, task_service=TaskService(TaskStore(f"{root}/tasks.sqlite3")))
            result = second.recover("recover-restart", [TaskAction("workspace.write", {"path": "fix", "content": "ok"})])
            self.assertTrue(result["ok"])
            self.assertEqual(result["state"]["attempts"], 1)

    def test_approve_restores_state_after_restart(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": True, "stage": "approval", "request_id": "restart-commit", "diff": "d"}
        workflow.approve.return_value = {"ok": True, "request_id": "restart-commit", "commit": {"ok": True}}
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            first = PlanExecutor(workflow, task_service=TaskService(store))
            prepared = first.prepare({
                "task_id": "restart-commit-task",
                "user_request": "restart then approve",
                "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
            })
            store.save_approval(
                "restart-commit",
                {"task_id": "restart-commit-task", "actions": [], "test_target": "tests",
                 "test_result": {"ok": True}, "diff": "d", "commit_result": None},
                "2026-09-30T10:00:00+00:00", "2099-09-30T10:00:00+00:00", "pending",
            )
            persisted_store = TaskStore(f"{root}/tasks.sqlite3")
            persisted_store.save_approval(
                "restart-commit",
                {
                    "task_id": "restart-commit-task",
                    "actions": [],
                    "test_target": "tests",
                    "test_result": {"ok": True},
                    "diff": "d",
                    "commit_result": {"ok": True},
                },
                "2026-09-30T10:00:00+00:00",
                "2099-09-30T10:00:00+00:00",
                "pending",
            )
            second = PlanExecutor(workflow, task_service=TaskService(persisted_store))
            result = second.approve("restart-commit", "reviewed change")
            self.assertTrue(result["ok"])
            self.assertEqual(result["state"]["task_id"], "restart-commit-task")
            self.assertEqual(result["state"]["stage"], "committed")
            restored = second.get_state("restart-commit-task")
            self.assertEqual(restored["stage"], "committed")
            self.assertEqual(restored["result"]["request_id"], "restart-commit")

    def test_get_state_unknown_task_raises(self):
        executor = PlanExecutor(Mock())
        with self.assertRaises(PlanExecutionError):
            executor.get_state("missing")


if __name__ == "__main__":
    unittest.main()
