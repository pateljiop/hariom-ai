import unittest

from app.tool_registry import ToolRegistry


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

    def test_computer_click_rejects_invalid_button_and_click_count(self):
        with self.assertRaises(Exception):
            self.registry.validate_arguments("computer.click", {"button": "invalid"})
        with self.assertRaises(Exception):
            self.registry.validate_arguments("computer.click", {"clicks": 0})


if __name__ == "__main__":
    unittest.main()
