import unittest
from unittest.mock import Mock

from app.task import Task, TaskStatus
from app.workstation import Workstation


class WorkstationRecoveryTests(unittest.TestCase):
    def test_awaiting_commit_approval_is_not_requeued(self):
        ws = Workstation.__new__(Workstation)
        ws.task_service = Mock()
        ws.queue = Mock()
        ws.activity = Mock()
        task = Task("task-bg-1", "request", "request", status=TaskStatus.AWAITING_COMMIT_APPROVAL)
        task.result = {"background": True}
        task.plan = {"actions": []}
        ws.task_service.list_tasks.return_value = [task]

        recovered = ws.recover_background_tasks()

        self.assertEqual(recovered, [])
        ws.queue.submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
