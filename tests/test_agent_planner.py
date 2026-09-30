import json
import unittest

from app.agent_planner import AgentPlanner, AgentPlanningError
from app.tool_registry import ToolRegistry


class AgentPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = AgentPlanner(ToolRegistry())

    def test_parses_valid_structured_plan(self):
        plan = self.planner.parse({
            "actions": [{
                "tool": "workspace.write",
                "arguments": {"path": "hello.txt", "content": "hello"},
            }],
        })
        self.assertEqual(plan.actions[0].tool, "workspace.write")

    def test_rejects_unknown_tool(self):
        with self.assertRaises(AgentPlanningError):
            self.planner.parse({
                "actions": [{"tool": "no.such.tool", "arguments": {}}],
            })

    def test_rejects_missing_required_argument(self):
        with self.assertRaises(AgentPlanningError):
            self.planner.parse({
                "actions": [{"tool": "workspace.write", "arguments": {"path": "a"}}],
            })

    def test_parse_json_rejects_invalid_json(self):
        with self.assertRaises(AgentPlanningError):
            self.planner.parse_json("{bad")

    def test_parse_json_accepts_valid_json(self):
        output = json.dumps({
            "actions": [{
                "tool": "workspace.read",
                "arguments": {"path": "hello.txt"},
            }],
        })
        self.assertEqual(self.planner.parse_json(output).actions[0].tool, "workspace.read")


if __name__ == "__main__":
    unittest.main()
