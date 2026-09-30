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

    def test_structured_steps_are_canonical_and_round_trip(self):
        plan = TaskPlan.from_dict({
            "steps": [{
                "step_id": "write",
                "tool": "workspace.write",
                "arguments": {"path": "a.txt", "content": "x"},
                "dependencies": [],
                "expected_files": ["a.txt"],
                "test_commands": ["tests"],
                "risk_level": "medium",
                "required_approvals": ["workspace.write"],
            }]
        })
        self.assertEqual(plan.steps[0].step_id, "write")
        self.assertEqual(plan.steps[0].risk_level, "medium" if isinstance(plan.steps[0].risk_level, str) else plan.steps[0].risk_level)
        data = plan.to_dict()
        self.assertEqual(data["steps"][0]["step_id"], "write")
        self.assertEqual(data["actions"][0]["tool"], "workspace.write")

    def test_steps_are_accepted_without_legacy_actions(self):
        plan = TaskPlan.from_dict({
            "steps": [{"step_id": "list", "tool": "workspace.list"}]
        })
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.actions[0].tool, "workspace.list")

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
