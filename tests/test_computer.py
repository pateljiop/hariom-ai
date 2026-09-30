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
            self.assertIn("computer_click_target", registry.names())
            self.assertIn("computer_type", registry.names())
            self.assertTrue(registry.get("computer_click").requires_approval)


    def test_tab_outside_top_region_is_rejected_before_click(self):
        activity = Mock()
        locator = Mock(return_value={
            "found": True, "x": 200, "y": 410, "confidence": 0.90, "label": "GitHub tab"
        })
        verifier = Mock()
        controller = ComputerController(activity, locator=locator, state_verifier=verifier)
        controller.screenshot_bytes = Mock(return_value=b"before")
        controller.screen_size = Mock(return_value={"width": 1280, "height": 720})
        controller.click = Mock()
        with self.assertRaisesRegex(RuntimeError, "outside the browser tab region"):
            controller.click_target("GitHub tab")
        controller.click.assert_not_called()
        verifier.assert_not_called()

    def test_click_requires_post_click_verification(self):
        activity = Mock()
        locator = Mock(return_value={
            "found": True, "x": 200, "y": 30, "confidence": 0.90, "label": "GitHub tab"
        })
        verifier = Mock(return_value={
            "verified": False, "confidence": 0.95, "reason": "tab is not active"
        })
        controller = ComputerController(activity, locator=locator, state_verifier=verifier)
        controller.screenshot_bytes = Mock(side_effect=[b"before", b"after"])
        controller.screen_size = Mock(return_value={"width": 1280, "height": 720})
        controller.click = Mock(return_value={"clicked": True, "x": 200, "y": 30, "button": "left"})
        controller.wait = Mock(return_value={"waited": 0.35})
        with self.assertRaisesRegex(RuntimeError, "tab is not active"):
            controller.click_target("GitHub tab")
        controller.click.assert_called_once()
        self.assertEqual(controller.screenshot_bytes.call_count, 2)

    def test_verified_click_returns_verified_result(self):
        activity = Mock()
        locator = Mock(return_value={
            "found": True, "x": 200, "y": 30, "confidence": 0.90, "label": "GitHub tab"
        })
        verifier = Mock(return_value={
            "verified": True, "confidence": 0.92, "reason": "GitHub tab is active"
        })
        controller = ComputerController(activity, locator=locator, state_verifier=verifier)
        controller.screenshot_bytes = Mock(side_effect=[b"before", b"after"])
        controller.screen_size = Mock(return_value={"width": 1280, "height": 720})
        controller.click = Mock(return_value={"clicked": True, "x": 200, "y": 30, "button": "left"})
        controller.wait = Mock(return_value={"waited": 0.35})
        result = controller.click_target("GitHub tab")
        self.assertTrue(result["clicked"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["verification_confidence"], 0.92)

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
