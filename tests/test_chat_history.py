import tempfile
import unittest
from pathlib import Path

from app.chat_history import ChatHistoryStore


class ChatHistoryTests(unittest.TestCase):
    def test_save_search_and_load_conversation(self):
        with tempfile.TemporaryDirectory() as d:
            store = ChatHistoryStore(Path(d) / "history.sqlite3")
            store.add("c1", "user", "how do I deploy this?")
            store.add("c1", "assistant", "Use Cloudflare Pages.")
            store.add("c2", "user", "Python testing")

            results = store.search("deploy")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["conversation_id"], "c1")

            conversation = store.conversation("c1")
            self.assertEqual([x["role"] for x in conversation], ["user", "assistant"])
            self.assertIn("Cloudflare", conversation[1]["content"])

    def test_recent_history_is_newest_first(self):
        with tempfile.TemporaryDirectory() as d:
            store = ChatHistoryStore(Path(d) / "history.sqlite3")
            store.add("old", "user", "old message")
            store.add("new", "user", "new message")
            self.assertEqual(store.recent(1)[0]["conversation_id"], "new")


if __name__ == "__main__":
    unittest.main()
