import tempfile
import unittest
from pathlib import Path

from app.identity import IDENTITY, MODE_GUIDANCE, profile
from app.intelligence import PersonalIntelligence


class FakeMemory:
    def search(self, request, limit=8):
        return [{"content": "prefers Hinglish", "kind": "preference"}]

    def important(self, limit=6):
        return [{"content": "Hariom AI project", "kind": "project"}]

    def recent(self, limit=5):
        return []


class FakeWorkspace:
    root = Path(tempfile.gettempdir()) / "hariom-ai-test"


class FakeTools:
    def describe(self):
        return [{"name": "read_file"}]


class FakeSkills:
    def catalog(self):
        return [{"name": "coding", "description": "software development"}]

    def instructions_for(self, request):
        return ["Inspect before editing."]


class PersonalIntelligenceTests(unittest.TestCase):
    def test_identity_policy(self):
        self.assertEqual(IDENTITY["name"], "Hariom AI")
        self.assertIn("English or Hinglish", IDENTITY["language_policy"])
        self.assertIn("coding", MODE_GUIDANCE)

    def test_profile_falls_back_to_general(self):
        self.assertEqual(profile("unknown")["mode"], "general")

    def test_build_combines_personal_context(self):
        intel = PersonalIntelligence(FakeMemory(), FakeWorkspace(), FakeTools(), FakeSkills())
        data = intel.build("fix my Python project", "coding")
        self.assertEqual(data["identity"]["name"], "Hariom AI")
        self.assertEqual(data["mode"], "coding")
        self.assertEqual(data["memory"]["relevant"][0]["kind"], "preference")
        self.assertEqual(data["skills"]["instructions"][0], "Inspect before editing.")
        self.assertEqual(data["tools"][0]["name"], "read_file")
        self.assertTrue(data["workspace_root"])

    def test_system_prompt_enforces_language_and_verification(self):
        prompt = PersonalIntelligence.system_prompt()
        self.assertIn("English or Hinglish", prompt)
        self.assertIn("Never claim an action happened", prompt)


if __name__ == "__main__":
    unittest.main()
