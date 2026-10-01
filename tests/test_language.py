import unittest

from app.language import command_context, normalize_text


class LanguageNormalizationTests(unittest.TestCase):
    def test_common_hinglish_shortcuts(self):
        self.assertEqual(normalize_text("github tab pr click kro"), "github tab par click karo")
        self.assertEqual(normalize_text("file bnao"), "file banao")
        self.assertEqual(normalize_text("isko shi kro"), "isko sahi karo")

    def test_technical_terms_are_preserved(self):
        self.assertEqual(normalize_text("openrouter API key check karo"), "openrouter API key check karo")

    def test_command_context(self):
        ctx = command_context("github tab pe click kro")
        self.assertEqual(ctx["language"], "hinglish")
        self.assertTrue(ctx["is_short_command"])
        self.assertEqual(ctx["normalized"], "github tab par click karo")


if __name__ == "__main__":
    unittest.main()
