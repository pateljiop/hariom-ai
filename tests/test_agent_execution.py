import unittest
from unittest.mock import Mock

from app.agent_execution import AgentExecutionFacade


class AgentExecutionFacadeTests(unittest.TestCase):
    def test_model_plan_is_validated_before_executor(self):
        executor = Mock()
        executor.workflow.executor.registry = Mock()
        executor.workflow.executor.registry.describe.return_value = [{
            "name": "workspace.read",
            "description": "read",
            "requires_approval": False,
            "schema": {"required": ["path"], "optional": []},
        }]
        executor.prepare.return_value = {"ok": True, "request_id": "r"}
        facade = AgentExecutionFacade(executor=executor)

        result = facade.prepare_model_output({
            "actions": [{"tool": "workspace.read", "arguments": {"path": "a.txt"}}],
        })

        self.assertTrue(result["ok"])
        executor.prepare.assert_called_once()
        payload = executor.prepare.call_args.args[0]
        self.assertEqual(payload["actions"][0]["tool"], "workspace.read")

    def test_invalid_model_plan_never_reaches_executor(self):
        executor = Mock()
        executor.workflow.executor.registry = Mock()
        executor.workflow.executor.registry.describe.return_value = []
        facade = AgentExecutionFacade(executor=executor)

        with self.assertRaises(Exception):
            facade.prepare_model_output({
                "actions": [{"tool": "unknown", "arguments": {}}],
            })
        executor.prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
