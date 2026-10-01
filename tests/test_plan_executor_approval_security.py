import unittest
from unittest.mock import Mock

from app.plan_executor import PlanExecutor, PlanExecutionError
from app.task import Task, TaskStatus


class PlanExecutorApprovalSecurityTests(unittest.TestCase):
    def test_approve_does_not_commit_non_pending_task(self):
        task_service = Mock()
        task = Task("task-1", "request", "request", status=TaskStatus.FAILED)
        task_service.store.get_approval.return_value = {"task_id": "task-1"}
        task_service.get_task.return_value = task
        workflow = Mock()
        executor = PlanExecutor(task_service=task_service, workflow=workflow)

        with self.assertRaises(PlanExecutionError):
            executor.approve("approval-1", "commit")

        workflow.approve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
