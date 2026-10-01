import time
import unittest
from app.task_queue import TaskQueue, TaskQueueError


class TaskQueueTests(unittest.TestCase):
    def test_submit_and_status(self):
        q = TaskQueue(1)
        try:
            q.submit("t1", lambda: {"ok": True})
            for _ in range(20):
                result = q.status("t1")
                if result["status"] == "completed":
                    break
                time.sleep(0.01)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["result"]["ok"], True)
        finally:
            q.shutdown()

    def test_duplicate_running_task_is_blocked(self):
        q = TaskQueue(1)
        try:
            q.submit("t1", time.sleep, 0.2)
            with self.assertRaises(TaskQueueError):
                q.submit("t1", lambda: None)
        finally:
            q.cancel("t1")
            q.shutdown()

    def test_cancel_unknown_task(self):
        q = TaskQueue(1)
        try:
            with self.assertRaises(TaskQueueError):
                q.cancel("missing")
        finally:
            q.shutdown()


if __name__ == "__main__":
    unittest.main()
