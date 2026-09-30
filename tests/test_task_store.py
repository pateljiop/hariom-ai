import tempfile
import unittest

from app.task import Task, TaskStatus
from app.task_store import TaskStore


class TaskStoreTests(unittest.TestCase):
    def test_create_get_and_update_survive_store_instances(self):
        with tempfile.TemporaryDirectory() as root:
            path = f"{root}/tasks.sqlite3"
            store = TaskStore(path)
            task = Task("task-1", "do x", "x")
            store.create(task)
            task.transition(TaskStatus.PLANNING)
            task.transition(TaskStatus.VALIDATING)
            task.transition(TaskStatus.EXECUTING)
            store.save(task)

            restored = TaskStore(path).get("task-1")
            self.assertEqual(restored.status, TaskStatus.EXECUTING)
            self.assertEqual(restored.task_id, "task-1")

    def test_events_persist(self):
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            task = Task("task-2", "do x", "x")
            store.create(task)
            task.transition(TaskStatus.PLANNING)
            event = task.transition(TaskStatus.VALIDATING)
            store.save(task)
            store.append_event(task.task_id, event)

            events = TaskStore(f"{root}/tasks.sqlite3").events("task-2")
            self.assertEqual(events[-1]["status"], "validating")

    def test_foreign_keys_are_enabled_for_events_and_approvals(self):
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            with self.assertRaises(Exception):
                store.append_event("missing-task", {"status": "x", "timestamp": "now"})
            with self.assertRaises(Exception):
                store.save_approval("approval-1", {"task_id": "missing-task"}, "now", "later")

    def test_duplicate_create_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            store.create(Task("task-3", "x", "x"))
            with self.assertRaises(ValueError):
                store.create(Task("task-3", "x", "x"))


if __name__ == "__main__":
    unittest.main()
