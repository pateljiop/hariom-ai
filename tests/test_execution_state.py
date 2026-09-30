import unittest

from app.execution_state import ExecutionState


class ExecutionStateTests(unittest.TestCase):
    def test_tracks_transitions_and_snapshot(self):
        state = ExecutionState("task-1")
        state.transition("planning", tool_count=2)
        state.result = {"ok": True}
        snapshot = state.snapshot()

        self.assertEqual(snapshot["task_id"], "task-1")
        self.assertEqual(snapshot["stage"], "planning")
        self.assertEqual(snapshot["events"][0]["tool_count"], 2)
        self.assertTrue(snapshot["result"]["ok"])

    def test_retry_is_bounded(self):
        state = ExecutionState("task-2", max_attempts=2)
        self.assertTrue(state.record_attempt())
        self.assertTrue(state.record_attempt())
        self.assertFalse(state.record_attempt())
        self.assertEqual(state.attempts, 2)

    def test_retry_event_is_recorded(self):
        state = ExecutionState("task-3")
        state.record_attempt()
        self.assertEqual(state.events[-1]["stage"], "retry")
        self.assertEqual(state.events[-1]["attempt"], 1)


if __name__ == "__main__":
    unittest.main()
