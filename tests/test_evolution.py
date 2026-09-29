import tempfile
import unittest
from pathlib import Path
from app.evolution import EvolutionEngine


class EvolutionEngineTests(unittest.TestCase):
    def test_proposes_and_records_upgrade(self):
        with tempfile.TemporaryDirectory() as d:
            engine = EvolutionEngine(Path(d))
            weaknesses = [{"area": "computer_click_target", "evidence": "not found"}]
            proposals = engine.propose(weaknesses)
            self.assertTrue(proposals)
            self.assertTrue(proposals[0]["production_merge_requires_approval"])
            engine.record(proposals)
            self.assertEqual(len(engine.review()), 1)


if __name__ == "__main__":
    unittest.main()
