import unittest
from unittest.mock import Mock

from app.agent_execution import AgentExecutionFacade
from app.agent_runner import AgentRunError, AgentRunner


class AgentRunnerTests(unittest.TestCase):
    def setUp(self):
        self.router = Mock()
        self.registry = Mock()
        self.registry.describe.return_value = [{
            "name": "workspace.read",
            "description": "read",
            "requires_approval": False,
            "schema": {"required": ["path"], "optional": []},
        }]
        self.facade = AgentExecutionFacade(
            tool_registry=self.registry,
            executor=Mock(),
        )
        self.runner = AgentRunner(self.router, self.facade)

    def test_plan_uses_router_and_validates_model_json(self):
        self.router.chat.return_value = (
            '{"actions":[{"tool":"workspace.read","arguments":{"path":"a.txt"}}]}',
            "fast",
        )
        plan = self.runner.plan("Read a.txt")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["provider"], "fast")
        self.assertEqual(plan["plan"]["actions"][0]["tool"], "workspace.read")
        self.router.chat.assert_called_once()

    def test_invalid_model_output_is_blocked(self):
        self.router.chat.return_value = ('{"actions":[{"tool":"unknown","arguments":{}}]}', "fast")
        with self.assertRaises(AgentRunError):
            self.runner.plan("do something")

    def test_prepare_keeps_execution_behind_validated_plan(self):
        self.router.chat.return_value = (
            '{"actions":[{"tool":"workspace.read","arguments":{"path":"a.txt"}}]}',
            "fast",
        )
        self.facade.prepare_model_output = Mock(return_value={"ok": True, "stage": "approval"})
        result = self.runner.prepare("Read a.txt")
        self.assertTrue(result["ok"])
        self.facade.prepare_model_output.assert_called_once()
        payload = self.facade.prepare_model_output.call_args.args[0]
        self.assertEqual(payload["actions"][0]["tool"], "workspace.read")
        self.assertEqual(result["provider"], "fast")

    def test_provider_failure_is_wrapped(self):
        self.router.chat.side_effect = RuntimeError("no provider")
        with self.assertRaises(AgentRunError):
            self.runner.plan("Read a.txt")


if __name__ == "__main__":
    unittest.main()
