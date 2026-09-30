import tempfile
import unittest

from app.task import TaskStatus
from app.task_service import TaskNotFoundError, TaskService
from app.task_store import TaskStore


class TaskServiceTests(unittest.TestCase):
    def test_create_and_reload_task(self):
        with tempfile.TemporaryDirectory() as root:
            service = TaskService(TaskStore(f"{root}/tasks.sqlite3"))
            task = service.create_task("Read README")
            self.assertTrue(task.task_id.startswith("task-"))
            restored = service.get_task(task.task_id)
            self.assertEqual(restored.user_request, "Read README")

    def test_transition_and_event_are_persisted(self):
        with tempfile.TemporaryDirectory() as root:
            service = TaskService(TaskStore(f"{root}/tasks.sqlite3"))
            task = service.create_task("Run tests")
            service.transition(task.task_id, TaskStatus.PLANNING)
            service.transition(task.task_id, TaskStatus.VALIDATING)
            restored = service.get_task(task.task_id)
            self.assertEqual(restored.status, TaskStatus.TESTING)
            self.assertTrue(any(e["status"] == "testing" for e in service.events(task.task_id)))

    def test_cancel_persists(self):
        with tempfile.TemporaryDirectory() as root:
            service = TaskService(TaskStore(f"{root}/tasks.sqlite3"))
            task = service.create_task("Cancel me")
            service.cancel_task(task.task_id)
            self.assertEqual(service.get_task(task.task_id).status, TaskStatus.CANCELLED)

    def test_unknown_task_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            service = TaskService(TaskStore(f"{root}/tasks.sqlite3"))
            with self.assertRaises(TaskNotFoundError):
                service.get_task("missing")


if __name__ == "__main__":
    unittest.main()
