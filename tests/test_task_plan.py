import unittest

from app.task_plan import PlanValidationError, TaskPlan


class TaskPlanTests(unittest.TestCase):
    def test_parses_json_friendly_plan(self):
        plan = TaskPlan.from_dict({
            "actions": [
                {"tool": "workspace.write", "arguments": {"path": "a.txt", "content": "x"}},
                {"tool": "tests.run", "arguments": {"target": "tests"}},
            ]
        })
        self.assertEqual(plan.actions[0].tool, "workspace.write")
        self.assertEqual(plan.to_dict()["actions"][1]["tool"], "tests.run")

    def test_defaults_arguments_and_test_target(self):
        plan = TaskPlan.from_dict({
            "actions": [{"tool": "workspace.list"}]
        })
        self.assertEqual(plan.actions[0].arguments, {})
        self.assertEqual(plan.test_target, "tests")

    def test_rejects_missing_or_empty_actions(self):
        for payload in ({}, {"actions": []}, {"actions": "bad"}):
            with self.subTest(payload=payload):
                with self.assertRaises(PlanValidationError):
                    TaskPlan.from_dict(payload)

    def test_rejects_malformed_action(self):
        cases = [
            {"actions": [{"arguments": {}}]},
            {"actions": [{"tool": "workspace.write", "arguments": []}]},
            {"actions": [{"tool": "workspace.write", "approved": "yes"}]},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(PlanValidationError):
                    TaskPlan.from_dict(payload)

    def test_rejects_empty_test_target(self):
        with self.assertRaises(PlanValidationError):
            TaskPlan.from_dict({
                "actions": [{"tool": "workspace.list"}],
                "test_target": "",
            })


if __name__ == "__main__":
    unittest.main()
