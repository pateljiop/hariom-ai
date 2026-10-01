"""Controlled self-improvement proposal lifecycle.

An evolution proposal can be prepared and tested on an isolated branch, but
commit/merge remain behind the existing explicit approval boundary.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


class EvolutionError(Exception):
    pass


@dataclass
class EvolutionProposal:
    proposal_id: str
    problem: str
    hypothesis: str
    branch: str
    repair_plan: dict
    status: str = "proposed"
    evidence: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvolutionEngine:
    def __init__(self, git, planner=None):
        self.git = git
        self.planner = planner
        self.proposals = {}

    def propose(self, problem, hypothesis, repair_plan):
        if not all(isinstance(v, str) and v.strip() for v in (problem, hypothesis)):
            raise EvolutionError("problem and hypothesis are required.")
        if not isinstance(repair_plan, dict):
            raise EvolutionError("repair_plan must be an object.")
        proposal_id = "evo-" + uuid.uuid4().hex
        branch = "evolution/" + proposal_id
        proposal = EvolutionProposal(
            proposal_id, problem.strip(), hypothesis.strip(), branch, dict(repair_plan)
        )
        self.proposals[proposal_id] = proposal
        return proposal

    def prepare_branch(self, proposal_id):
        proposal = self._get(proposal_id)
        if proposal.status != "proposed":
            raise EvolutionError("Only proposed upgrades can enter implementation.")
        self.git.create_branch(proposal.branch)
        proposal.status = "implementing"
        return proposal

    def record_verification(self, proposal_id, result):
        proposal = self._get(proposal_id)
        if not isinstance(result, dict):
            raise EvolutionError("Verification result must be an object.")
        proposal.evidence.append(dict(result))
        proposal.status = "verified" if result.get("ok") else "failed"
        return proposal

    def request_merge(self, proposal_id):
        proposal = self._get(proposal_id)
        if proposal.status != "verified":
            raise EvolutionError("Only verified upgrades can request merge approval.")
        proposal.status = "awaiting_merge_approval"
        return {
            "ok": True,
            "proposal_id": proposal.proposal_id,
            "branch": proposal.branch,
            "evidence": list(proposal.evidence),
            "requires_human_approval": True,
        }

    def merge(self, proposal_id, approved=False):
        proposal = self._get(proposal_id)
        if proposal.status != "awaiting_merge_approval":
            raise EvolutionError("Upgrade is not awaiting merge approval.")
        if not approved:
            raise PermissionError("Human approval is required to merge an evolution proposal.")
        result = self.git.merge_branch(proposal.branch, approved=True)
        proposal.status = "merged"
        proposal.evidence.append({"merge": result})
        return {"ok": True, "proposal_id": proposal_id, "result": result}

    def _get(self, proposal_id):
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise EvolutionError("Unknown evolution proposal.")
        return proposal
