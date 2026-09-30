import unittest

from app.tool_registry import ToolError, ToolRegistry


class ToolSchemaEnforcementTests(unittest.TestCase):
    def test_missing_required_argument_rejected_before_handler(self):
        registry = ToolRegistry()
        with self.assertRaises(ToolError):
            registry.execute("workspace.read", {})

    def test_unknown_argument_rejected(self):
        registry = ToolRegistry()
        with self.assertRaises(ToolError):
            registry.execute("workspace.read", {"path": "x.txt", "extra": True})

    def test_wrong_argument_type_rejected(self):
        registry = ToolRegistry()
        with self.assertRaises(ToolError):
            registry.execute("workspace.write", {"path": "x.txt", "content": 123})

    def test_describe_includes_schema_fields(self):
        registry = ToolRegistry()
        item = next(x for x in registry.describe() if x["name"] == "workspace.write")
        self.assertEqual(item["schema"]["required"], ["path", "content"])


if __name__ == "__main__":
    unittest.main()
