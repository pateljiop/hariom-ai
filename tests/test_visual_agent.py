import unittest
from unittest.mock import Mock

from app.visual_agent import VisualAgent, VisualAgentError


class VisualAgentTests(unittest.TestCase):
    def test_parse_json_decision(self):
        self.assertEqual(VisualAgent._parse('{"done":true}'), {"done": True})

    def test_parse_rejects_non_json(self):
        with self.assertRaises(VisualAgentError):
            VisualAgent._parse("not json")

    def test_browser_uses_router_and_loop(self):
        router = Mock()
        router.chat.return_value = ('{"done":true}', "fast")
        registry = Mock()
        registry.execute.return_value = {"ok": True, "result": {"url": "http://example.test"}}
        agent = VisualAgent(router, registry)
        result = agent.browser("finish the task")
        self.assertTrue(result["ok"])
        router.chat.assert_called_once()

    def test_computer_uses_vision_router(self):
        router = Mock()
        router.chat_vision.return_value = ('{"done":true}', "vision")
        registry = Mock()
        registry.execute.side_effect = [
            {"ok": True, "result": {"width": 1200, "height": 800}},
            {"ok": True, "result": "/tmp/screen.png"},
        ]
        agent = VisualAgent(router, registry, approval_checker=lambda _: True)
        agent._screen_size_for_test = True
        # The computer loop fingerprints the returned file; use a real temp file.
        import tempfile
        from pathlib import Path
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"screen")
            path = f.name
        registry.execute.side_effect = [
            {"ok": True, "result": {"width": 1200, "height": 800}},
            {"ok": True, "result": path},
        ]
        result = agent.computer("observe screen")
        self.assertTrue(result["ok"])
        router.chat_vision.assert_called_once()
        Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
