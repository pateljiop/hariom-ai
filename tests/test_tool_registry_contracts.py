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
