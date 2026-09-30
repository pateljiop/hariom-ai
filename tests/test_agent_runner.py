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
        self.registry.validate_arguments.return_value = True
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
        self.registry.validate_arguments.side_effect = ValueError("Unknown tool: unknown")
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

    def test_run_performs_bounded_repair(self):
        self.router.chat.side_effect = [
            ('{"actions":[{"tool":"workspace.read","arguments":{"path":"a.txt"}}]}', "fast"),
            ('{"actions":[{"tool":"workspace.write","arguments":{"path":"a.txt","content":"fixed"}}]}', "fast"),
        ]
        self.facade.prepare_model_output = Mock(return_value={"ok": False, "stage": "verification", "state": {"task_id": "task-1"}})
        self.facade.executor.recover = Mock(return_value={"ok": True, "stage": "approval", "state": {"task_id": "task-1"}})
        result = self.runner.run("Fix a.txt", max_repairs=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["repairs"], 1)
        self.facade.executor.recover.assert_called_once()
        self.assertEqual(self.facade.executor.recover.call_args.args[0], "task-1")

    def test_run_rejects_excessive_repair_budget(self):
        with self.assertRaises(AgentRunError):
            self.runner.run("Fix it", max_repairs=4)

    def test_provider_failure_is_wrapped(self):
        self.router.chat.side_effect = RuntimeError("no provider")
        with self.assertRaises(AgentRunError):
            self.runner.plan("Read a.txt")


if __name__ == "__main__":
    unittest.main()


class TrustBoundaryTests(unittest.TestCase):
    def test_planning_prompt_marks_external_content_untrusted(self):
        prompt = AgentRunner._planning_prompt([])
        self.assertIn("UNTRUSTED DATA", prompt)
        self.assertIn("Only direct user intent", prompt)
        self.assertIn("bypass approval", prompt)


if __name__ == "__main__":
    unittest.main()
