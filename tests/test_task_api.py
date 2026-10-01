import tempfile
import unittest

from app.task_api import TaskAPI, TaskAPIError
from app.task_service import TaskService
from app.task_store import TaskStore
from app.tool_registry import ToolRegistry
from app.workspace import Workspace


class TaskAPITests(unittest.TestCase):
    def make_api(self, root):
        workspace = Workspace(root)
        registry = ToolRegistry(workspace=workspace)
        service = TaskService(TaskStore(f"{root}/tasks.sqlite3"))
        from app.plan_executor import PlanExecutor
        executor = PlanExecutor(task_service=service)
        executor.workflow.executor.registry = registry
        executor.workflow.git = registry.git
        return TaskAPI(
            task_service=service,
            executor=executor,
            workflow=executor.workflow,
            tool_registry=registry,
        )

    def test_create_get_and_events_endpoint_contract(self):
        with tempfile.TemporaryDirectory() as root:
            api = self.make_api(root)
            created = api.create_task({"user_request": "Read README"})
            task_id = created["task"]["task_id"]
            fetched = api.get_task(task_id)
            self.assertEqual(fetched["task"]["task_id"], task_id)
            self.assertEqual(api.get_events(task_id)["events"], [])

    def test_validate_and_preview_reject_invalid_tool(self):
        with tempfile.TemporaryDirectory() as root:
            api = self.make_api(root)
            task_id = api.create_task({"user_request": "Do something"})["task"]["task_id"]
            with self.assertRaises(TaskAPIError):
                api.validate_task(task_id, {
                    "task_id": task_id,
                    "user_request": "Do something",
                    "steps": [{"step_id": "s1", "tool": "does.not.exist", "arguments": {}}],
                })

    def test_preview_reports_approval_for_high_risk_tool(self):
        with tempfile.TemporaryDirectory() as root:
            api = self.make_api(root)
            task_id = api.create_task({"user_request": "Run a command"})["task"]["task_id"]
            preview = api.preview_task(task_id, {
                "task_id": task_id,
                "user_request": "Run a command",
                "steps": [{
                    "step_id": "s1",
                    "tool": "terminal.run",
                    "arguments": {"command": "echo hello", "approved": False},
                    "risk_level": "high",
                    "required_approvals": ["terminal"],
                }],
            })
            self.assertTrue(preview["approval_required"])
            self.assertEqual(preview["actions"][0]["permission"], "terminal.execute")

    def test_approval_is_task_bound(self):
        with tempfile.TemporaryDirectory() as root:
            api = self.make_api(root)
            first = api.create_task({"user_request": "one"})["task"]["task_id"]
            second = api.create_task({"user_request": "two"})["task"]["task_id"]
            with self.assertRaises(TaskAPIError):
                api.approve_task(first, "approval-missing", "commit")
            self.assertNotEqual(first, second)

    def test_cancel_endpoint(self):
        with tempfile.TemporaryDirectory() as root:
            api = self.make_api(root)
            task_id = api.create_task({"user_request": "cancel me"})["task"]["task_id"]
            result = api.cancel_task(task_id)
            self.assertEqual(result["task"]["status"], "cancelled")

    def test_diff_endpoint_for_new_task_is_empty(self):
        with tempfile.TemporaryDirectory() as root:
            api = self.make_api(root)
            task_id = api.create_task({"user_request": "no diff"})["task"]["task_id"]
            self.assertEqual(api.get_diff(task_id)["diff"], "")

    def test_endpoint_contract_is_complete(self):
        expected = {
            "POST /tasks", "GET /tasks/{task_id}", "POST /tasks/{task_id}/validate",
            "POST /tasks/{task_id}/preview", "POST /tasks/{task_id}/execute",
            "POST /tasks/{task_id}/cancel", "POST /tasks/{task_id}/approve",
            "POST /tasks/{task_id}/reject", "GET /tasks/{task_id}/events",
            "GET /tasks/{task_id}/diff",
        }
        self.assertEqual(set(TaskAPI.ENDPOINTS), expected)


if __name__ == "__main__":
    unittest.main()
