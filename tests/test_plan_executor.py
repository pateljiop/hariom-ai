import unittest
from unittest.mock import Mock

from app.plan_executor import PlanExecutor


class PlanExecutorTests(unittest.TestCase):
    def test_prepare_converts_plan_and_returns_review_payload(self):
        workflow = Mock()
        workflow.prepare.return_value = {"ok": True, "stage": "approval", "request_id": "abc", "diff": "d"}
        executor = PlanExecutor(workflow)

        result = executor.prepare({
            "actions": [{"tool": "workspace.write", "arguments": {"path": "a", "content": "b"}}],
            "test_target": "tests",
        })

        workflow.prepare.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual(result["request_id"], "abc")
        self.assertEqual(result["plan"]["test_target"], "tests")

    def test_prepare_rejects_malformed_external_plan(self):
        executor = PlanExecutor(Mock())
        with self.assertRaises(Exception):
            executor.prepare({"actions": []})

    def test_approve_delegates_explicit_approval(self):
        workflow = Mock()
        workflow.approve.return_value = {"ok": True}
        executor = PlanExecutor(workflow)

        result = executor.approve("abc", "reviewed change")

        workflow.approve.assert_called_once_with("abc", "reviewed change")
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
