import unittest

from app.task_engine import TaskState, TaskStatus


class TaskStateTests(unittest.TestCase):
    def test_progress_and_phase_follow_task_state(self):
        state = TaskState("demo")
        state.add_step("first")
        state.add_step("second")
        self.assertEqual(state.progress, 0)
        self.assertEqual(state.phase, "Planning")

        state.status = TaskStatus.RUNNING
        state.start_step(0)
        state.finish_step("ok")
        self.assertEqual(state.progress, 50)
        self.assertEqual(state.phase, "Running")

        state.status = TaskStatus.VERIFYING
        self.assertEqual(state.phase, "Verifying")

    def test_timeline_exposes_safe_step_metadata(self):
        state = TaskState("demo")
        state.add_step("Open file", "read_file", {"path": "x"})
        state.add_step("Write file", "write_file", {"path": "x", "content": "secret"})
        timeline = state.timeline()

        self.assertEqual(timeline[0]["index"], 1)
        self.assertEqual(timeline[0]["tool"], "read_file")
        self.assertEqual(timeline[1]["status"], "pending")
        self.assertNotIn("content", timeline[1])


if __name__ == "__main__":
    unittest.main()
