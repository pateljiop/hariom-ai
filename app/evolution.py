import json
import time
from pathlib import Path
import re
from .evolution_developer import EvolutionDeveloper


class EvolutionEngine:
    """Controlled self-improvement: observe weaknesses, propose upgrades, keep history."""

    def __init__(self, root, activity=None):
        self.root = Path(root)
        self.activity = activity
        self.path = self.root / "evolution_history.json"
        self.root.mkdir(parents=True, exist_ok=True)

    def observe_task(self, state):
        failures = list(getattr(state, "errors", []) or [])
        failed_steps = [
            step for step in getattr(state, "steps", [])
            if step.get("status") == "failed"
        ]
        weaknesses = []
        for step in failed_steps:
            weaknesses.append({
                "area": str(step.get("tool") or "agent"),
                "evidence": str(step.get("output", ""))[-1000:],
                "description": str(step.get("description", "")),
            })
        for error in failures[-5:]:
            if not any(error == item["evidence"] for item in weaknesses):
                weaknesses.append({"area": "runtime", "evidence": str(error)[-1000:]})
        if weaknesses:
            self._emit("EVOLUTION -> weakness detected: %s" % len(weaknesses))
        return weaknesses

    def propose(self, weaknesses):
        proposals = []
        for item in weaknesses[:10]:
            area = item.get("area", "agent")
            if area == "computer_click_target":
                action = "Improve screen-target parsing/verification and add a regression test."
            elif area.startswith("browser_"):
                action = "Improve browser action handling and add a regression test."
            elif area in {"write_file", "run_command"}:
                action = "Improve protected-tool validation and add a regression test."
            else:
                action = "Inspect the failure, implement the smallest safe fix, and add a regression test."
            proposals.append({
                "area": area,
                "evidence": item.get("evidence", ""),
                "upgrade": action,
                "production_merge_requires_approval": True,
            })
        return proposals

    def record(self, proposals, status="proposed"):
        history = self._load()
        entry = {
            "timestamp": time.time(),
            "status": str(status),
            "proposals": proposals,
        }
        history.append(entry)
        self.path.write_text(
            json.dumps(history[-100:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._emit("EVOLUTION -> recorded %s upgrade proposal(s)" % len(proposals))
        return entry

    def develop_candidate(self, router, repo_root, request, weaknesses):
        """Generate and test a candidate on an isolated branch; never merge it."""
        if not weaknesses:
            raise ValueError("weaknesses are required")
        slug = re.sub(r"[^a-z0-9-]+", "-", str(request).lower()).strip("-")[:40] or "upgrade"
        branch = "evolution/" + slug + "-" + str(int(time.time()))
        developer = EvolutionDeveloper(repo_root, self.activity)
        developer.create_isolated_branch(branch)
        prompt = ("Act as a careful maintainer. Produce ONLY a unified git diff patch. "
                  "Fix the documented weakness with the smallest safe change. Add tests when appropriate. "
                  "Do not modify secrets or deployment credentials.\n\nREQUEST:\n" + str(request) +
                  "\nWEAKNESSES:\n" + json.dumps(weaknesses, ensure_ascii=False))
        message, provider = router.chat(prompt, system="You are the Hariom AI evolution developer. Return a unified diff only; no markdown fences.", profile="hariom/coding")
        developer.apply_patch(message)
        tests = developer.run_tests()
        if not tests["passed"]:
            self.record([{"area":"evolution","evidence":tests["output"],"upgrade":"Repair candidate before review.","production_merge_requires_approval":True}], status="candidate_failed")
            return {"branch":branch,"provider":provider,"tests":tests,"ready_for_review":False}
        diff = developer.diff()
        if not diff.strip():
            raise RuntimeError("Candidate produced no diff.")
        commit = developer.commit_candidate("evolution: " + slug)
        result = {"branch":branch,"provider":provider,"tests":tests,"commit":commit,"ready_for_review":True}
        self.record([{"area":"evolution","evidence":str(weaknesses),"upgrade":"Candidate tested on isolated branch.","production_merge_requires_approval":True,"candidate":result}], status="candidate_ready")
        return result
    def review(self):
        return self._load()[-20:]

    def _load(self):
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError, TypeError):
            return []

    def _emit(self, message):
        if self.activity:
            self.activity.emit(message)
