from pathlib import Path


class Verifier:
    """Evidence-based checks for common local tool outcomes."""

    def verify_step(self, step):
        tool = step.get("tool")
        output = step.get("output", "")
        if step.get("status") != "completed":
            return False, "step did not complete"
        if tool and not output:
            return False, "tool returned no observable output"

        args = step.get("arguments") or {}
        if tool == "write_file":
            path = args.get("path")
            if not path:
                return False, "write_file has no target path"
            target = Path(step.get("workspace_root", "")) / path
            if step.get("workspace_root") and not target.is_file():
                return False, "written file was not found after the tool reported success"

        return True, "verified"

    def verify_task(self, state):
        failures = []
        for step in state.steps:
            ok, reason = self.verify_step(step)
            if not ok:
                failures.append(reason)
        return not failures, failures
