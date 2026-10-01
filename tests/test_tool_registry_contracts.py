import unittest

from app.tool_registry import ToolApprovalRequired, ToolRegistry


class ToolRegistryContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_all_registered_tools_expose_explicit_input_and_return_contracts(self):
        descriptions = self.registry.describe()
        self.assertGreater(len(descriptions), 0)
        for tool in descriptions:
            self.assertIn("input_schema", tool)
            self.assertIn("return_schema", tool)
            self.assertIsInstance(tool["input_schema"], dict)
            self.assertIsInstance(tool["return_schema"], dict)

    def test_browser_find_is_registered_and_read_only(self):
        self.assertTrue(self.registry.validate_arguments("browser.find", {"selector": "button"}))
        spec = next(item for item in self.registry.describe() if item["name"] == "browser.find")
        self.assertEqual(spec["risk"], "low")
        self.assertFalse(spec["requires_approval"])
        self.assertEqual(spec["permission"], "browser.read")

    def test_browser_read_accepts_selector(self):
        self.assertTrue(self.registry.validate_arguments("browser.read", {"selector": "#main"}))

    def test_browser_open_requires_external_network_approval(self):
        spec = next(item for item in self.registry.describe() if item["name"] == "browser.open")
        self.assertTrue(spec["requires_approval"])
        self.assertEqual(spec["permission"], "external_network")

    def test_sensitive_input_requires_secrets_access(self):
        with self.assertRaises(ToolApprovalRequired):
            self.registry.execute("browser.type", {"selector": "#password", "text": "secret", "sensitive": True}, approved=True)

    def test_trusted_approval_token_executes_task_bound_tool_once(self):
        token = self.registry.permission_manager.issue_approval_token(
            task_id="task-1", tool="workspace.write",
            permission="workspace.write",
            arguments={"path": "token.txt", "content": "ok"},
            ttl_seconds=60,
        )
        result = self.registry.execute(
            "workspace.write",
            {"path": "token.txt", "content": "ok"},
            task_id="task-1",
            approval_token=token,
        )
        self.assertTrue(result["ok"])
        with self.assertRaises(ToolApprovalRequired):
            self.registry.execute(
                "workspace.write",
                {"path": "token.txt", "content": "ok"},
                task_id="task-1",
                approval_token=token,
            )

    def test_sensitive_selector_requires_bound_secrets_token(self):
        args = {"selector": "#password", "text": "secret"}
        with self.assertRaises(ToolApprovalRequired):
            self.registry.execute("browser.type", args, approved=True)
        token = self.registry.permission_manager.issue_approval_token(
            task_id="task-sensitive", tool="browser.type",
            permission=["browser.type", "secrets_access"],
            arguments=args, ttl_seconds=60,
        )
        self.registry.browser.type_text = lambda **kwargs: True
        result = self.registry.execute(
            "browser.type", args, task_id="task-sensitive",
            approval_token=token,
        )
        self.assertTrue(result["ok"])

    def test_side_effect_browser_click_requires_extra_permission(self):
        args = {"selector": "#submit"}
        with self.assertRaises(ToolApprovalRequired):
            self.registry.execute("browser.click", args, approved=True)
        token = self.registry.permission_manager.issue_approval_token(
            task_id="task-side-effect", tool="browser.click",
            permission=["browser.click", "external_side_effect"],
            arguments=args, ttl_seconds=60,
        )
        self.registry.browser.click = lambda **kwargs: True
        result = self.registry.execute(
            "browser.click", args, task_id="task-side-effect",
            approval_token=token,
        )
        self.assertTrue(result["ok"])

    def test_legacy_approval_dict_is_not_authorization(self):
        with self.assertRaises(ToolApprovalRequired):
            self.registry.execute(
                "browser.open",
                {"url": "https://example.com"},
                approved=True,
                task_id="task-1",
                approval={"task_id": "task-1", "tool": "browser.open", "permission": "external_network"},
            )

    def test_computer_hotkey_requires_approval(self):
        spec = next(item for item in self.registry.describe() if item["name"] == "computer.hotkey")
        self.assertTrue(spec["requires_approval"])
        self.assertEqual(spec["permission"], "computer.keyboard")
        self.assertTrue(self.registry.validate_arguments("computer.hotkey", {"keys": ["ctrl", "c"]}))

    def test_computer_click_rejects_invalid_button_and_click_count(self):
        with self.assertRaises(Exception):
            self.registry.validate_arguments("computer.click", {"button": "invalid"})
        with self.assertRaises(Exception):
            self.registry.validate_arguments("computer.click", {"clicks": 0})


if __name__ == "__main__":
    unittest.main()
