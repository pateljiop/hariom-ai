import unittest
from unittest.mock import Mock

from app.tools import ToolRegistry


class VoiceToolTests(unittest.TestCase):
    def test_voice_tools_are_registered(self):
        voice = Mock()
        registry = ToolRegistry(Mock(), Mock(), voice=voice)
        self.assertIn("voice_listen", registry.names())
        self.assertIn("voice_speak", registry.names())
        self.assertFalse(registry.get("voice_listen").requires_approval)

    def test_voice_listen_is_explicitly_invoked(self):
        voice = Mock()
        registry = ToolRegistry(Mock(), Mock(), voice=voice)
        registry.execute("voice_listen", {"timeout": 1, "phrase_time_limit": 2})
        voice.listen.assert_called_once_with(timeout=1, phrase_time_limit=2)


if __name__ == "__main__":
    unittest.main()
