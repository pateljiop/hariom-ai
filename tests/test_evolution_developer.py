import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from app.evolution_developer import EvolutionDeveloper


class EvolutionDeveloperTests(unittest.TestCase):
    def test_rejects_dirty_repository_before_branch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "x.txt").write_text("x", encoding="utf-8")
            dev = EvolutionDeveloper(root, Mock())
            # The class must use git commands; a non-repository cannot silently proceed.
            with self.assertRaises(Exception):
                dev.status()


if __name__ == "__main__":
    unittest.main()
