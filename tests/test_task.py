import unittest

from app.task import RiskLevel, Task, TaskStatus, TaskStep


class TaskTests(unittest.TestCase):
    def test_task_defaults_to_created_low_risk_and_two_retries(self):
        task = Task("task-1", "do x", "x")
        self.assertEqual(task.status, TaskStatus.CREATED)
        self.assertEqual(task.risk_level, RiskLevel.LOW)
        self.assertEqual(task.max_retries, 2)

    def test_task_transition_records_event(self):
        task = Task("task-2", "do x", "x")
        event = task.transition(TaskStatus.EXECUTING, tool="workspace.write")
        self.assertEqual(task.status, TaskStatus.EXECUTING)
        self.assertEqual(event["status"], "executing")
        self.assertEqual(event["tool"], "workspace.write")

    def test_task_step_round_trips(self):
        step = TaskStep("s1", "workspace.read", {"path": "a.txt"}, risk_level=RiskLevel.MEDIUM)
        task = Task("task-3", "read", "read file", steps=(step,))
        data = task.to_dict()
        self.assertEqual(data["steps"][0]["tool"], "workspace.read")
        self.assertEqual(data["steps"][0]["risk_level"], "medium")

    def test_string_step_risk_is_normalized(self):\n        step = TaskStep("s2", "workspace.read", risk_level="medium")\n        self.assertEqual(step.risk_level, RiskLevel.MEDIUM)\n\n    def test_invalid_retry_limit_rejected(self):
        with self.assertRaises(ValueError):
            Task("task-4", "x", "x", max_retries=11)


if __name__ == "__main__":
    unittest.main()
