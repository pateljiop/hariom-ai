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

    def tearDown(self):
        ai_router.PROVIDERS.clear()
        ai_router.PROVIDERS.update(self.original)

    def test_available_only_returns_configured_providers(self):
        ai_router.PROVIDERS['missing'] = {
            'key': '',
            'model': 'missing-model',
            'base': 'https://example.test/missing',
        }
        self.assertEqual(self.router.available(), ['fast', 'fallback'])

    def test_failed_provider_enters_cooldown(self):
        self.router._failure('fast')
        status = self.router.status()
        self.assertFalse(status['fast']['healthy'])
        self.assertGreater(status['fast']['cooldown_remaining'], 0)

    def test_success_updates_latency_and_health(self):
        self.router._success('fast', 1.25)
        status = self.router.status()
        self.assertTrue(status['fast']['healthy'])
        self.assertEqual(status['fast']['successes'], 1)
        self.assertAlmostEqual(status['fast']['latency'], 1.25)

    @patch.object(ai_router.AIRouter, '_compatible')
    def test_chat_falls_back_to_next_provider(self, compatible):
        compatible.side_effect = [RuntimeError('rate limited'), 'ok']

        text, provider = self.router.chat('hello')

        self.assertEqual(text, 'ok')
        self.assertEqual(provider, 'fallback')
        self.assertEqual(compatible.call_count, 2)
        self.assertFalse(self.router.status()['fast']['healthy'])

    @patch.object(ai_router.AIRouter, '_compatible')
    def test_preferred_provider_is_tried_first(self, compatible):
        compatible.return_value = 'preferred-ok'

        text, provider = self.router.chat('hello', preferred='fallback')

        self.assertEqual(text, 'preferred-ok')
        self.assertEqual(provider, 'fallback')
        self.assertEqual(
            compatible.call_args.args[0]['key'],
            'key-fallback',
        )


if __name__ == '__main__':
    unittest.main()
