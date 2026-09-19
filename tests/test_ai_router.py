import unittest
from unittest.mock import Mock, patch

from app.ai_router import AIRouter


class Activity:
    def __init__(self):
        self.events = []

    def emit(self, message):
        self.events.append(message)


def response(status, payload):
    r = Mock()
    r.status_code = status
    r.text = str(payload)
    r.json.return_value = payload
    if status >= 400:
        import requests
        r.raise_for_status.side_effect = requests.HTTPError(response=r)
    return r


class RouterRetryTests(unittest.TestCase):
    def setUp(self):
        self.activity = Activity()
        self.router = AIRouter(self.activity)
        self.cfg = {
            "key": "test-key",
            "model": "test-model",
            "base": "https://example.test/v1/chat/completions",
        }

    @patch("app.ai_router.time.sleep")
    @patch("app.ai_router.requests.post")
    def test_retries_transient_error_then_succeeds(self, post, sleep):
        post.side_effect = [
            response(503, {"error": "temporary"}),
            response(503, {"error": "temporary"}),
            response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]

        result = self.router._compatible(self.cfg, "hello", "")

        self.assertEqual(result, "ok")
        self.assertEqual(post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertIn("retrying in 1s", self.activity.events[0])
        self.assertIn("retrying in 2s", self.activity.events[1])

    @patch("app.ai_router.time.sleep")
    @patch("app.ai_router.requests.post")
    def test_does_not_retry_billing_error(self, post, sleep):
        post.return_value = response(402, {"error": "payment required"})

        with self.assertRaises(Exception):
            self.router._compatible(self.cfg, "hello", "")

        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
