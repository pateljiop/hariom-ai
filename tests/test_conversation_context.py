import unittest
from app.conversation_context import build_context

class ConversationContextTests(unittest.TestCase):
    def test_preserves_recent_context_and_system(self):
        messages = [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
        ]
        result = build_context(messages, "system")
        self.assertEqual(result[0]["role"], "system")
        self.assertEqual([m["content"] for m in result[1:]], ["one", "two", "three"])

    def test_context_is_bounded(self):
        messages = [{"role": "user", "content": "x" * 100} for _ in range(10)]
        result = build_context(messages, max_messages=4, max_chars=250)
        self.assertLessEqual(len(result) - 1, 4)
        self.assertLessEqual(sum(len(m["content"]) for m in result[1:]), 250)

if __name__ == "__main__":
    unittest.main()
