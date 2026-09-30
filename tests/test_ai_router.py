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
    def test_locate_on_screen_parses_normalized_bbox(self, vision):
        vision.return_value = ("<box>[[0, 240, 40, 450]]</box>", "openrouter")
        result = self.router.locate_on_screen("GitHub tab", b"image", (1280, 720))
        self.assertTrue(result["found"])
        self.assertEqual(result["x"], 442)
        self.assertEqual(result["y"], 14)

    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_locate_on_screen_parses_pixel_bbox(self, vision):
        vision.return_value = ("[615, 8, 925, 45]", "openrouter")
        result = self.router.locate_on_screen("GitHub tab", b"image", (1280, 720))
        self.assertTrue(result["found"])
        self.assertEqual(result["x"], 770)
        self.assertEqual(result["y"], 26)

    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_verify_click_state_requires_confident_verified_json(self, vision):
        vision.return_value = (
            '{"verified":true,"confidence":0.91,"reason":"GitHub tab is active"}',
            "openai",
        )
        result = self.router.verify_click_state("GitHub tab", b"image", (1280, 720))
        self.assertTrue(result["verified"])
        self.assertEqual(result["confidence"], 0.91)

    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_verify_click_state_rejects_unverified_json(self, vision):
        vision.return_value = (
            '{"verified":false,"confidence":0.95,"reason":"GitHub tab is visible but inactive"}',
            "openai",
        )
        result = self.router.verify_click_state("GitHub tab", b"image", (1280, 720))
        self.assertFalse(result["verified"])

    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_locate_on_screen_crops_browser_tab_region(self, vision):
        vision.return_value = (
            '{"found":true,"x":300,"y":120,"label":"GitHub tab","confidence":0.91}',
            "openrouter",
        )
        result = self.router.locate_on_screen("GitHub tab", b"image", (1280, 1080))
        self.assertTrue(result["found"])
        self.assertEqual(result["x"], 300)
        self.assertEqual(result["y"], 120)
        vision.assert_called_once()
        self.assertIn("cropped image", vision.call_args.args[0])
        self.assertEqual(vision.call_args.args[1], b"image")

    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_locate_on_screen_uses_top_crop_for_real_image(self, vision):
        from PIL import Image
        import io
        image = Image.new("RGB", (100, 100), "white")
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        vision.return_value = (
            '{"found":true,"x":40,"y":10,"label":"GitHub tab","confidence":0.91}',
            "openrouter",
        )
        result = self.router.locate_on_screen("GitHub tab", buf.getvalue(), (100, 100))
        self.assertTrue(result["found"])
        self.assertEqual(result["y"], 10)
        sent_image = vision.call_args.args[1]
        with Image.open(io.BytesIO(sent_image)) as sent:
            self.assertEqual(sent.size, (100, 18))
    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_locate_on_screen_recovers_wrapped_json_and_aliases(self, vision):
        vision.return_value = (
            'Here is the result: {"bbox":[615,8,925,45],"confidence":0.91,"label":"GitHub tab"} done.',
            "openrouter",
        )
        result = self.router.locate_on_screen("GitHub tab", b"image", (1280, 720))
        self.assertTrue(result["found"])
        self.assertEqual(result["x"], 770)
        self.assertEqual(result["y"], 26)

    @patch.object(ai_router.AIRouter, "vision_chat")
    def test_locate_on_screen_recovers_coordinate_alias(self, vision):
        vision.return_value = (
            'Result: {"coordinates":{"x":320,"y":90},"confidence":0.91,"label":"Save"}',
            "openrouter",
        )
        result = self.router.locate_on_screen("Save button", b"image", (800, 600))
        self.assertTrue(result["found"])
        self.assertEqual(result["x"], 320)
        self.assertEqual(result["y"], 90)

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
