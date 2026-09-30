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

    def test_enum_and_nested_schema_validation(self):\n        from app.tool_schema import ToolSchema, ToolSchemaError\n        nested = ToolSchema(required=("mode",), enums={"mode": ("safe", "fast")})\n        schema = ToolSchema(required=("config",), types={"config": (dict,)}, nested={"config": nested})\n        schema.validate({"config": {"mode": "safe"}})\n        with self.assertRaises(ToolSchemaError):\n            schema.validate({"config": {"mode": "unsafe"}})\n\n    def test_describe_includes_schema_fields(self):
        registry = ToolRegistry()
        item = next(x for x in registry.describe() if x["name"] == "workspace.write")
        self.assertEqual(item["schema"]["required"], ["path", "content"])


if __name__ == "__main__":
    unittest.main()
