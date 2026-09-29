import unittest
from unittest.mock import Mock, patch

from app import ai_router


class AIRouterTests(unittest.TestCase):
    def setUp(self):
        self.activity = Mock()
        self.router = ai_router.AIRouter(self.activity)
        self.original = ai_router.PROVIDERS.copy()
        ai_router.PROVIDERS.clear()
        ai_router.PROVIDERS.update({
            "fast": {"key":"key-fast","model":"fast-model","base":"https://example.test/fast"},
            "fallback": {"key":"key-fallback","model":"fallback-model","base":"https://example.test/fallback"},
        })
        # Router health is persisted for the real app; tests must start from an isolated state.
        self.router.health.clear()

    def tearDown(self):
        ai_router.PROVIDERS.clear()
        ai_router.PROVIDERS.update(self.original)

    def test_available_only_returns_configured_providers(self):
        ai_router.PROVIDERS["missing"]={"key":"","model":"missing-model","base":"https://example.test/missing"}
        self.assertEqual(self.router.available(),["fast","fallback"])

    def test_failed_provider_enters_cooldown(self):
        self.router._failure("fast",RuntimeError("rate limited"))
        status=self.router.status()
        self.assertFalse(status["fast"]["healthy"])
        self.assertGreater(status["fast"]["cooldown_remaining"],0)

    def test_success_updates_latency_and_health(self):
        self.router._success("fast",1.25)
        status=self.router.status()
        self.assertTrue(status["fast"]["healthy"])
        self.assertEqual(status["fast"]["successes"],1)
        self.assertAlmostEqual(status["fast"]["latency"],1.25)

    @patch.object(ai_router.AIRouter,"_compatible_request")
    def test_chat_falls_back_to_next_provider(self, request):
        request.side_effect=[RuntimeError("429 rate limited"),({"role":"assistant","content":"ok"}, {})]
        text,provider=self.router.chat("hello")
        self.assertEqual(text,"ok")
        self.assertEqual(provider,"fallback")
        self.assertEqual(request.call_count,2)
        self.assertFalse(self.router.status()["fast"]["healthy"])

    @patch.object(ai_router.AIRouter,"_compatible_request")
    def test_preferred_provider_is_tried_first(self, request):
        request.return_value=({"role":"assistant","content":"preferred-ok"}, {})
        text,provider=self.router.chat("hello",preferred="fallback")
        self.assertEqual(text,"preferred-ok")
        self.assertEqual(provider,"fallback")
        self.assertEqual(request.call_args.args[0], "fallback")

    def test_profiles_include_auto_and_coding(self):
        self.assertIn("hariom/auto",self.router.profiles())
        self.assertIn("hariom/coding",self.router.profiles())

    def test_tool_requests_skip_unsupported_provider(self):
        ai_router.PROVIDERS["fast"]["supports_tools"]=False
        ai_router.PROVIDERS["fallback"]["supports_tools"]=True
        ranked=self.router._rank(tools=[{"type":"function"}])
        self.assertTrue(all(name=="fallback" for name,_ in ranked))


    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_locate_on_screen_parses_and_clamps(self, vision):
        vision.return_value = (
            '{"found":true,"x":9999,"y":-20,"label":"Save","confidence":0.91}',
            "openai",
        )
        result = self.router.locate_on_screen("Save button", b"image", (800, 600))
        self.assertTrue(result["found"])
        self.assertEqual(result["x"], 799)
        self.assertEqual(result["y"], 0)
        self.assertEqual(result["label"], "Save")

    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_locate_on_screen_rejects_low_confidence(self, vision):
        vision.return_value = (
            '{"found":true,"x":100,"y":100,"confidence":0.42}',
            "openai",
        )
        result = self.router.locate_on_screen("Save button", b"image", (800, 600))
        self.assertFalse(result["found"])
        self.assertIn("confidence", result["reason"])

    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_locate_on_screen_accepts_not_found(self, vision):
        vision.return_value = (
            '{"found":false,"reason":"Not visible"}',
            "openai",
        )
        result = self.router.locate_on_screen("Save button", b"image", (800, 600))
        self.assertFalse(result["found"])
        self.assertEqual(result["reason"], "Not visible")

    def test_auth_failure_enters_long_disable_window(self):
        self.router._failure("fast",RuntimeError("401 Unauthorized"))
        self.assertGreater(self.router.status()["fast"]["disabled_remaining"],80000)

if __name__=="__main__":
    unittest.main()
