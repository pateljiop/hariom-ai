import unittest
from unittest.mock import Mock, patch

from app import ai_router


class AIRouterTests(unittest.TestCase):
    def setUp(self):
        self.activity = Mock()
        self.router = ai_router.AIRouter(self.activity)
        self.original = ai_router.PROVIDERS.copy()
        self.cache_enabled = ai_router.CACHE_ENABLED
        ai_router.CACHE_ENABLED = False
        ai_router.PROVIDERS.clear()
        ai_router.PROVIDERS.update({
            'fast': {
                'key': 'key-fast',
                'model': 'fast-model',
                'base': 'https://example.test/fast',
            },
            'fallback': {
                'key': 'key-fallback',
                'model': 'fallback-model',
                'base': 'https://example.test/fallback',
            },
        })
        # Keep tests isolated from router health persisted by earlier tests.
        self.router.health.clear()

    def tearDown(self):
        ai_router.PROVIDERS.clear()
        ai_router.PROVIDERS.update(self.original)
        ai_router.CACHE_ENABLED = self.cache_enabled

    def test_available_only_returns_configured_providers(self):
        ai_router.PROVIDERS['missing'] = {
            'key': '',
            'model': 'missing-model',
            'base': 'https://example.test/missing',
        }
        self.assertEqual(self.router.available(), ['fast', 'fallback'])

    def test_failed_provider_enters_cooldown(self):
        self.router._failure('fast', RuntimeError('rate limited'))
        status = self.router.status()
        self.assertFalse(status['fast']['healthy'])
        self.assertGreater(status['fast']['cooldown_remaining'], 0)

    def test_success_updates_latency_and_health(self):
        self.router._success('fast', 1.25)
        status = self.router.status()
        self.assertTrue(status['fast']['healthy'])
        self.assertEqual(status['fast']['successes'], 1)
        self.assertAlmostEqual(status['fast']['latency'], 1.25)

    @patch.object(ai_router.AIRouter, '_compatible_request')
    def test_chat_falls_back_to_next_provider(self, compatible):
        compatible.side_effect = [
            RuntimeError('rate limited'),
            ({'role': 'assistant', 'content': 'ok'}, {}),
        ]

        text, provider = self.router.chat('hello')

        self.assertEqual(text, 'ok')
        self.assertEqual(provider, 'fallback')
        self.assertEqual(compatible.call_count, 2)
        self.assertFalse(self.router.status()['fast']['healthy'])

    @patch.object(ai_router.AIRouter, '_compatible_request')
    def test_preferred_provider_is_tried_first(self, compatible):
        compatible.return_value = ({'role': 'assistant', 'content': 'preferred-ok'}, {})

        text, provider = self.router.chat('hello', preferred='fallback')

        self.assertEqual(text, 'preferred-ok')
        self.assertEqual(provider, 'fallback')
        self.assertEqual(compatible.call_args.args[0], 'fallback')
        self.assertEqual(compatible.call_args.args[1]['key'], 'key-fallback')

    def test_profiles_include_auto_and_coding(self):
        self.assertIn('hariom/auto', self.router.profiles())
        self.assertIn('hariom/coding', self.router.profiles())

    def test_tool_requests_skip_unsupported_provider(self):
        ai_router.PROVIDERS['fast']['supports_tools'] = False
        ai_router.PROVIDERS['fallback']['supports_tools'] = True
        ranked = self.router._rank(tools=[{'type': 'function'}])
        self.assertTrue(all(name == 'fallback' for name, _ in ranked))

    def test_auth_failure_enters_long_disable_window(self):
        self.router._failure('fast', RuntimeError('401 Unauthorized'))
        status = self.router.status()['fast']
        self.assertGreater(status['disabled_remaining'], 80000)


if __name__ == '__main__':
    unittest.main()
