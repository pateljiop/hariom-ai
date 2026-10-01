import unittest
from unittest.mock import Mock

from app.agent_execution import AgentExecutionFacade
from app.agent_runner import AgentRunError, AgentRunner


class AgentToolLoopTests(unittest.TestCase):
    def setUp(self):
        self.router = Mock()
        self.registry = Mock()
        self.registry.describe.return_value = [{
            "name": "workspace.read",
            "description": "Read a file",
            "requires_approval": False,
            "risk": "low",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }]
        self.registry.execute.return_value = {
            "ok": True,
            "tool": "workspace.read",
            "result": "hello",
        }
        self.facade = AgentExecutionFacade(tool_registry=self.registry, executor=Mock())
        self.runner = AgentRunner(self.router, self.facade)

    def test_tool_loop_executes_tool_then_returns_final_answer(self):
        self.router.chat_request.side_effect = [
            ({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "workspace.read", "arguments": '{"path":"a.txt"}'},
                }],
            }, "fast"),
            ({"role": "assistant", "content": "The file says hello."}, "fast"),
        ]

        result = self.runner.run_tool_loop("Read a.txt", max_iterations=3)

        self.assertTrue(result["ok"])
        self.assertEqual(result["response"], "The file says hello.")
        self.registry.execute.assert_called_once_with(
            "workspace.read", {"path": "a.txt"}, approved=False
        )
        sent = self.router.chat_request.call_args_list[1].args[0]
        self.assertEqual(sent[-1]["role"], "tool")
        self.assertEqual(sent[-1]["tool_call_id"], "call-1")

    def test_risky_tool_requires_human_approval(self):
        self.registry.describe.return_value = [{
            "name": "git.commit",
            "description": "Commit changes",
            "requires_approval": True,
            "risk": "high",
            "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}},
        }]
        self.router.chat_request.return_value = ({
            "role": "assistant",
            "tool_calls": [{
                "id": "call-2",
                "type": "function",
                "function": {"name": "git.commit", "arguments": '{"message":"test"}'},
            }],
        }, "fast")

        result = self.runner.run_tool_loop("Commit the changes")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "awaiting_approval")
        self.registry.execute.assert_not_called()

    def test_risky_tool_executes_only_after_approval(self):
        self.registry.describe.return_value = [{
            "name": "git.commit",
            "description": "Commit changes",
            "requires_approval": True,
            "risk": "high",
            "input_schema": {"type": "object"},
        }]
        self.router.chat_request.side_effect = [
            ({"role": "assistant", "tool_calls": [{
                "id": "call-3", "type": "function",
                "function": {"name": "git.commit", "arguments": '{"message":"test"}'},
            }]}, "fast"),
            ({"role": "assistant", "content": "Committed."}, "fast"),
        ]

        result = self.runner.run_tool_loop(
            "Commit the changes", approval_checker=lambda action: action["tool"] == "git.commit"
        )

        self.assertTrue(result["ok"])
        self.registry.execute.assert_called_once_with(
            "git.commit", {"message": "test"}, approved=True
        )

    def test_tool_loop_is_bounded(self):
        self.router.chat_request.return_value = ({
            "role": "assistant",
            "tool_calls": [{
                "id": "call-loop",
                "type": "function",
                "function": {"name": "workspace.read", "arguments": '{"path":"a.txt"}'},
            }],
        }, "fast")
        result = self.runner.run_tool_loop("Keep reading", max_iterations=4)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "loop_detected")
        self.assertEqual(self.registry.execute.call_count, 4)

    def test_invalid_tool_call_is_rejected(self):
        self.router.chat_request.return_value = ({
            "role": "assistant",
            "tool_calls": [{
                "id": "call-bad", "type": "function",
                "function": {"name": "not-registered", "arguments": "{}"},
            }],
        }, "fast")
        with self.assertRaises(AgentRunError):
            self.runner.run_tool_loop("Do something")


if __name__ == "__main__":
    unittest.main()
