import json
from .terminal import run_command


class Agent:
    """Small, safety-first execution loop for the Windows v1 agent."""

    MAX_STEPS = 8
    MAX_READ_CHARS = 20000
    MAX_RESULT_CHARS = 6000

    def __init__(self, router, workspace, activity):
        self.router = router
        self.workspace = workspace
        self.activity = activity

    def run(self, task):
        self.activity.emit("AGENT -> planning task")
        plan, provider = self.router.plan(task, self._planner_system())
        self.activity.emit(f"AGENT -> plan ready ({provider})")

        steps = plan.get("steps")
        if not isinstance(steps, list):
            raise ValueError("Agent plan is missing a steps list.")
        if len(steps) > self.MAX_STEPS:
            raise ValueError(f"Agent plan has too many steps (max {self.MAX_STEPS}).")

        results = []
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                results.append({"step": index, "error": "Invalid step object."})
                continue

            tool = step.get("tool")
            args = step.get("args") or {}
            self.activity.emit(f"AGENT -> step {index}/{len(steps)}: {tool}")

            try:
                result = self._execute(tool, args)
                results.append({"step": index, "tool": tool, "result": result})
                self.activity.emit(f"AGENT OK -> {tool}")
            except Exception as exc:
                error = str(exc)
                results.append({"step": index, "tool": tool, "error": error})
                self.activity.emit(f"AGENT BLOCKED/FAILED -> {tool}: {error}")

        summary = self._summarize(task, plan, results)
        self.activity.emit("AGENT -> task complete")
        return summary, results

    def _execute(self, tool, args):
        if tool == "list_workspace":
            files = self.workspace.list_files()
            return [str(path.relative_to(self.workspace.root)) for path in files[:300]]

        if tool == "read_file":
            path = args.get("path")
            if not isinstance(path, str) or not path.strip():
                raise ValueError("read_file requires a path.")
            text = self.workspace.read_file(path)
            return text[:self.MAX_READ_CHARS]

        if tool == "write_file":
            path = args.get("path")
            content = args.get("content")
            if not isinstance(path, str) or not path.strip():
                raise ValueError("write_file requires a path.")
            if not isinstance(content, str):
                raise ValueError("write_file requires string content.")
            if len(content) > 100000:
                raise ValueError("write_file content is too large for this v1 tool.")
            target = self.workspace.write_file(path, content)
            return f"Wrote {target.relative_to(self.workspace.root)} ({len(content)} chars)."

        if tool == "run_command":
            command = args.get("command")
            if not isinstance(command, str) or not command.strip():
                raise ValueError("run_command requires a command.")
            code, output = run_command(command, self.activity, cwd=self.workspace.root)
            return {
                "exit_code": code,
                "output": output[-self.MAX_RESULT_CHARS:],
            }

        raise ValueError(f"Unknown agent tool: {tool}")

    def _planner_system(self):
        return """You are the planning component of Hariom AI, a local Windows workstation agent.
Return ONLY valid JSON matching this exact shape:
{
  "steps": [
    {"tool": "list_workspace|read_file|write_file|run_command", "args": {}}
  ],
  "goal": "short description"
}

Rules:
- Use only the four listed tools.
- Paths for read_file/write_file are relative to the user's workspace.
- Never use absolute paths.
- Prefer inspecting the workspace before modifying existing files.
- Use write_file for creating or replacing files.
- Use run_command for tests/builds only when needed.
- Do not use destructive commands such as delete, format, shutdown, registry changes, force pushes, or disk operations.
- Keep the plan to the minimum steps needed.
- Never claim a tool ran; only describe intended steps.
"""

    def _summarize(self, task, plan, results):
        compact = json.dumps(results, ensure_ascii=False)
        prompt = f"""Task:
{task}

Planned steps:
{json.dumps(plan, ensure_ascii=False)}

Actual tool results:
{compact}

Give a concise factual completion report.
Separate:
1. What was done
2. Files changed (if any)
3. Commands/tests run and their exit codes
4. Anything blocked, failed, or still needing approval
Never claim an action happened unless it appears in the actual tool results."""
        text, _ = self.router.chat(prompt, system="You are the reporting component of Hariom AI. Report only verified tool results.")
        return text
