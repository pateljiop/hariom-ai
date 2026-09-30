import unittest

from app.tool_registry import ToolApprovalRequired, ToolError, ToolRegistry
from app.permissions import Permission, PermissionManager


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

    def test_enum_and_nested_schema_validation(self):
        from app.tool_schema import ToolSchema, ToolSchemaError
        nested = ToolSchema(required=("mode",), enums={"mode": ("safe", "fast")})
        schema = ToolSchema(required=("config",), types={"config": (dict,)}, nested={"config": nested})
        schema.validate({"config": {"mode": "safe"}})
        with self.assertRaises(ToolSchemaError):
            schema.validate({"config": {"mode": "unsafe"}})

    def test_central_permission_gate_blocks_unapproved_terminal(self):
        registry = ToolRegistry(permission_manager=PermissionManager())
        with self.assertRaises(ToolApprovalRequired):
            registry.validate_arguments("terminal.run", {"command": "echo ok"})
            registry.execute("terminal.run", {"command": "echo ok"})

    def test_explicit_approval_passes_permission_gate(self):
        registry = ToolRegistry(permission_manager=PermissionManager())
        self.assertTrue(registry.permission_manager.decide(Permission.TERMINAL_EXECUTE, approved=True).allowed)

    def test_requires_explicit_approval_even_when_permission_is_granted(self):
        registry = ToolRegistry()
        registry.permission_manager.grant(Permission.BROWSER_CLICK)
        with self.assertRaises(ToolApprovalRequired):
            registry.execute("browser.click", {"selector": "#submit"})

    def test_explicit_approval_allows_gated_tool(self):
        registry = ToolRegistry()
        registry.permission_manager.grant(Permission.BROWSER_CLICK)
        registry.browser.click = lambda selector, approved=False: {"selector": selector}
        result = registry.execute("browser.click", {"selector": "#submit"}, approved=True)
        self.assertTrue(result["ok"])

    def test_describe_includes_schema_fields(self):
        registry = ToolRegistry()
        item = next(x for x in registry.describe() if x["name"] == "workspace.write")
        self.assertEqual(item["schema"]["required"], ["path", "content"])


if __name__ == "__main__":
    unittest.main()
