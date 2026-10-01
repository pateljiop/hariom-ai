import unittest
from unittest.mock import Mock
from app.evolution import EvolutionEngine, EvolutionError


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.git = Mock()
        self.engine = EvolutionEngine(self.git)

    def test_proposal_branch_and_verification_flow(self):
        p = self.engine.propose("test failure", "repair regression", {"actions": []})
        self.assertEqual(p.status, "proposed")
        self.engine.prepare_branch(p.proposal_id)
        self.git.create_branch.assert_called_once_with(p.branch)
        self.engine.record_verification(p.proposal_id, {"ok": True, "tests": "green"})
        request = self.engine.request_merge(p.proposal_id)
        self.assertTrue(request["requires_human_approval"])
        self.engine.merge(p.proposal_id, approved=True)
        self.git.merge_branch.assert_called_once_with(p.branch, approved=True)

    def test_unverified_proposal_cannot_merge(self):
        p = self.engine.propose("failure", "fix", {})
        with self.assertRaises(EvolutionError):
            self.engine.request_merge(p.proposal_id)

    def test_merge_never_implicit(self):
        p = self.engine.propose("failure", "fix", {})
        self.engine.prepare_branch(p.proposal_id)
        self.engine.record_verification(p.proposal_id, {"ok": True})
        self.engine.request_merge(p.proposal_id)
        with self.assertRaises(PermissionError):
            self.engine.merge(p.proposal_id)


if __name__ == "__main__":
    unittest.main()
