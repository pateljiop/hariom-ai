import unittest

from app.task_executor import TaskAction, TaskExecutionError, TaskExecutor


class TaskExecutorValidationTests(unittest.TestCase):
    def test_duplicate_step_ids_are_rejected_without_dependencies(self):
        executor = TaskExecutor()
        actions = (
            TaskAction("workspace.list", {}, step_id="same"),
            TaskAction("workspace.list", {}, step_id="same"),
        )
        with self.assertRaisesRegex(TaskExecutionError, "Step IDs must be unique"):
            executor.validate(actions)


if __name__ == "__main__":
    unittest.main()
