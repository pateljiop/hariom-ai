import unittest
from unittest.mock import Mock, patch

from app.computer_loop import ComputerControlLoop, ComputerLoopError


class ComputerControlLoopTests(unittest.TestCase):
    def setUp(self):
        self.registry = Mock()

    @staticmethod
    def _ok(tool, result):
        return {"ok": True, "tool": tool, "result": result}

    def test_fingerprint_changes_when_screenshot_bytes_change(self):
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"first")
            path = handle.name
        try:
            first = ComputerControlLoop._fingerprint(path)
            with open(path, "wb") as handle:
                handle.write(b"second")
            second = ComputerControlLoop._fingerprint(path)
            self.assertNotEqual(first, second)
        finally:
            ComputerControlLoop._cleanup(path)

    def test_visual_loop_captures_after_action_and_completes(self):
        self.registry.execute.side_effect = [
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen1.png"),
            self._ok("computer.click", True),
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen2.png"),
        ]
        decisions = iter([
            {"action": {"tool": "computer.click", "arguments": {"x": 10, "y": 20}, "approved": True},
             "visual_state": {"summary": "button visible", "target_visible": True, "completed": False, "blocked": False}},
            {"done": True},
        ])
        with patch.object(ComputerControlLoop, "_fingerprint", side_effect=["before", "after"]):
            result = ComputerControlLoop(
                self.registry,
                approval_checker=lambda action: action["tool"] in {"computer.screenshot", "computer.click"},
            ).run(lambda image, history: next(decisions))
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["iterations"], 1)
        verification = result["history"][0]["visual_verification"]
        self.assertEqual(verification["before"], "before")
        self.assertEqual(verification["after"], "after")
        self.assertTrue(verification["changed"])
        self.assertEqual(result["history"][0]["visual_state"]["summary"], "button visible")

    def test_unchanged_visual_state_is_reported_without_forcing_failure(self):
        self.registry.execute.side_effect = [
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen1.png"),
            self._ok("computer.key", True),
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen2.png"),
        ]
        decisions = iter([
            {"action": {"tool": "computer.key", "arguments": {"key": "tab"}, "approved": True}},
            {"done": True},
        ])
        with patch.object(ComputerControlLoop, "_fingerprint", side_effect=["same", "same"]):
            result = ComputerControlLoop(
                self.registry,
                approval_checker=lambda action: True,
            ).run(lambda image, history: next(decisions))
        self.assertTrue(result["ok"])
        self.assertFalse(result["history"][0]["visual_verification"]["changed"])

    def test_repeated_unchanged_action_is_stopped(self):
        self.registry.execute.side_effect = [
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen1.png"),
            self._ok("computer.key", True),
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen2.png"),
        ]
        with patch.object(ComputerControlLoop, "_fingerprint", side_effect=["same", "same"]):
            result = ComputerControlLoop(
                self.registry,
                max_iterations=3,
                approval_checker=lambda action: True,
            ).run(lambda image, history: {
                "action": {"tool": "computer.key", "arguments": {"key": "tab"}, "approved": True}
            })
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "stagnated")
        self.assertEqual(self.registry.execute.call_count, 5)

    def test_visual_state_schema_is_bounded(self):
        state = ComputerControlLoop._validate_visual_state({
            "visual_state": {
                "summary": "dialog opened",
                "target_visible": True,
                "completed": False,
                "blocked": False,
            }
        })
        self.assertTrue(state["target_visible"])
        with self.assertRaises(ComputerLoopError):
            ComputerControlLoop._validate_visual_state({
                "visual_state": {"summary": "x", "unexpected": True}
            })
        with self.assertRaises(ComputerLoopError):
            ComputerControlLoop._validate_visual_state({
                "visual_state": {"summary": "x" * 1001}
            })

    def test_model_cannot_self_approve_desktop_action(self):
        self.registry.execute.return_value = {"ok": False, "error": "approval required"}
        self.registry.execute.side_effect = [
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            {"ok": False, "error": "approval required"},
        ]
        with patch.object(ComputerControlLoop, "_fingerprint", return_value="initial"):
            result = ComputerControlLoop(self.registry).run(
                lambda image, history: {
                    "action": {
                        "tool": "computer.click",
                        "arguments": {"x": 1, "y": 2},
                        "approved": True,
                    }
                },
                initial_image="/tmp/screen.png",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "action_failed")

    def test_click_outside_screen_is_rejected_before_action(self):
        self.registry.side_effect = None
        self.registry.execute.side_effect = [
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen.png"),
        ]
        with patch.object(ComputerControlLoop, "_fingerprint", return_value="initial"):
            with self.assertRaises(ComputerLoopError):
                ComputerControlLoop(self.registry).run(
                    lambda image, history: {
                        "action": {"tool": "computer.click", "arguments": {"x": 1920, "y": 100}, "approved": True}
                    }
                )

    def test_invalid_screen_geometry_is_rejected(self):
        self.registry.execute.return_value = self._ok(
            "computer.screen_size", {"width": 0, "height": 1080}
        )
        with self.assertRaises(ComputerLoopError):
            ComputerControlLoop(self.registry).run(lambda image, history: {"done": True})

    def test_non_desktop_tool_is_rejected(self):
        with self.assertRaises(ComputerLoopError):
            ComputerControlLoop(self.registry).run(
                lambda image, history: {
                    "action": {"tool": "terminal.run", "arguments": {"command": "whoami"}}
                },
                initial_image="/tmp/screen.png",
            )

    def test_iteration_limit_is_bounded(self):
        self.registry.execute.side_effect = [
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.key", True),
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen.png"),
            self._ok("computer.key", True),
            self._ok("computer.screen_size", {"width": 1920, "height": 1080}),
            self._ok("computer.screenshot", "/tmp/screen.png"),
        ]
        with patch.object(ComputerControlLoop, "_fingerprint", side_effect=["one", "two", "three"]):
            result = ComputerControlLoop(self.registry, max_iterations=2).run(
                lambda image, history: {
                    "action": {"tool": "computer.key", "arguments": {"key": "tab"}}
                },
                initial_image="/tmp/screen.png",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "iteration_limit")


if __name__ == "__main__":
    unittest.main()
