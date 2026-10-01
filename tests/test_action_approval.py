import tempfile
import unittest
from unittest.mock import Mock

from app.plan_executor import PlanExecutor
from app.task_service import TaskService
from app.task_store import TaskStore
from app.task_executor import TaskAction
from app.tool_registry import ToolRegistry


class ActionApprovalLifecycleTests(unittest.TestCase):
    def test_risky_plan_stops_before_execution(self):
        workflow = Mock()
        workflow.executor.registry.approval_requirements.return_value = [{
            "step_id": "s1", "tool": "terminal.run", "risk": "high",
            "permission": "terminal.execute", "reason": "explicit approval required",
        }]
        with tempfile.TemporaryDirectory() as root:
            service = TaskService(TaskStore(root + "/tasks.sqlite3"))
            executor = PlanExecutor(workflow, task_service=service)
            result = executor.prepare({
                "task_id": "approval-task",
                "actions": [{
                    "step_id": "s1",
                    "tool": "terminal.run",
                    "arguments": {"command": "echo safe"},
                }],
            })

            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "awaiting_approval")
            self.assertEqual(service.get_task("approval-task").status.value, "awaiting_approval")
            workflow.prepare.assert_not_called()

    def test_approved_actions_resume_normal_execution(self):
        workflow = Mock()
        workflow.executor.registry.approval_requirements.side_effect = [
            [{"step_id": "s1", "tool": "terminal.run", "risk": "high",
              "permission": "terminal.execute", "reason": "explicit approval required"}],
            [],
        ]
        workflow.prepare.return_value = {
            "ok": True, "stage": "approval", "request_id": "commit-1", "diff": "diff",
        }
        with tempfile.TemporaryDirectory() as root:
            service = TaskService(TaskStore(root + "/tasks.sqlite3"))
            executor = PlanExecutor(workflow, task_service=service)
            prepared = executor.prepare({
                "task_id": "approval-resume",
                "actions": [{
                    "step_id": "s1",
                    "tool": "terminal.run",
                    "arguments": {"command": "echo safe"},
                }],
            })

            result = executor.approve_actions(prepared["task_id"])

            self.assertTrue(result["ok"])
            self.assertEqual(result["request_id"], "commit-1")
            self.assertEqual(service.get_task("approval-resume").status.value, "awaiting_commit_approval")
            self.assertEqual(workflow.prepare.call_count, 1)

    def test_partial_action_approval_does_not_enter_execution(self):
        workflow = Mock()
        workflow.executor.registry.approval_requirements.side_effect = [
            [
                {"step_id": "s1", "tool": "terminal.run", "risk": "high",
                 "permission": "terminal.execute", "reason": "explicit approval required"},
                {"step_id": "s2", "tool": "browser.click", "risk": "high",
                 "permission": "browser.click", "reason": "explicit approval required"},
            ],
            [
                {"step_id": "s2", "tool": "browser.click", "risk": "high",
                 "permission": "browser.click", "reason": "explicit approval required"},
            ],
        ]
        with tempfile.TemporaryDirectory() as root:
            service = TaskService(TaskStore(root + "/tasks.sqlite3"))
            executor = PlanExecutor(workflow, task_service=service)
            prepared = executor.prepare({
                "task_id": "partial-approval",
                "actions": [
                    {"step_id": "s1", "tool": "terminal.run", "arguments": {"command": "echo safe"}},
                    {"step_id": "s2", "tool": "browser.click", "arguments": {"selector": "#x"}},
                ],
            })

            result = executor.approve_actions(prepared["task_id"], ["s1"])

            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "awaiting_approval")
            self.assertEqual(service.get_task("partial-approval").status.value, "awaiting_approval")
            workflow.prepare.assert_not_called()

    def test_registry_reports_only_unapproved_required_actions(self):
        registry = ToolRegistry()
        requirements = registry.approval_requirements([
            TaskAction("workspace.read", {"path": "README.md"}, step_id="read"),
            TaskAction("terminal.run", {"command": "echo safe"}, step_id="terminal"),
        ])
        self.assertEqual([item["step_id"] for item in requirements], ["terminal"])

    def test_plan_persistence_keeps_approval_metadata(self):
        from app.task_plan import TaskPlan
        plan = TaskPlan.from_dict({
            "actions": [{
                "step_id": "s1",
                "tool": "terminal.run",
                "arguments": {"command": "echo safe"},
                "approved": True,
            }]
        })
        restored = TaskPlan.from_dict(plan.to_dict())
        self.assertTrue(restored.actions[0].approved)
        self.assertEqual(restored.actions[0].step_id, "s1")


if __name__ == "__main__":
    unittest.main()
