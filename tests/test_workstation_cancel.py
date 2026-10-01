import unittest
from unittest.mock import Mock

from app.workstation import Workstation, WorkstationError


class WorkstationCancelTests(unittest.TestCase):
    def test_running_worker_is_not_marked_cancelled(self):
        ws = Workstation.__new__(Workstation)
        ws.queue = Mock()
        ws.queue.cancel.return_value = {"cancelled": False}
        ws.task_service = Mock()
        ws.activity = Mock()

        with self.assertRaises(WorkstationError):
            ws.cancel("task-1")

        ws.task_service.cancel_task.assert_not_called()

    def test_queued_worker_can_be_cancelled(self):
        ws = Workstation.__new__(Workstation)
        ws.queue = Mock()
        ws.queue.cancel.return_value = {"cancelled": True}
        ws.task_service = Mock()
        ws.activity = Mock()
        task = Mock(status=Mock(value="cancelled"))
        ws.task_service.cancel_task.return_value = task

        result = ws.cancel("task-1")

        ws.task_service.cancel_task.assert_called_once_with("task-1")
        self.assertTrue(result["cancelled"])


if __name__ == "__main__":
    unittest.main()
