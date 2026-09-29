import unittest
from unittest.mock import Mock, patch

from app.computer import ComputerController
from app.tools import ToolRegistry
from app.workspace import Workspace


class ComputerControllerTests(unittest.TestCase):
    def test_rejects_non_windows_without_touching_desktop(self):
        controller = ComputerController(Mock())
        controller.system = "Linux"
        with self.assertRaises(RuntimeError):
            controller.screen_size()

    def test_computer_tools_are_registered(self):
        with __import__("tempfile").TemporaryDirectory() as d:
            controller = ComputerController(Mock())
            registry = ToolRegistry(Workspace(d), Mock(), computer=controller)
            self.assertIn("computer_screenshot", registry.names())
            self.assertIn("computer_click", registry.names())
            self.assertIn("computer_type", registry.names())
            self.assertTrue(registry.get("computer_click").requires_approval)

    def test_mouse_bounds_are_checked(self):
        controller = ComputerController(Mock())
        controller.system = "Windows"
        fake = Mock()
        fake.size.return_value = type("Size", (), {"width": 100, "height": 100})()
        with patch.object(controller, "_pyautogui", return_value=fake):
            with self.assertRaises(ValueError):
                controller.move_mouse(100, 100)


if __name__ == "__main__":
    unittest.main()
