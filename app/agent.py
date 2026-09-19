import json
from .terminal import run_command
import subprocess
import re
from .terminal import RISKY_PATTERNS


class Agent:
    """Small, safety-first execution loop for the Windows v1 agent."""

    MAX_STEPS = 8
    MAX_READ_CHARS = 20000
    MAX_RESULT_CHARS = 6000
    MAX_ITERATIONS = 3
    GIT_TIMEOUT = 30

    def __init__(self, router, workspace, activity, approval_callback=None):
        self.router = router
        self.workspace = workspace
        self.activity = activity
        self.approval_callback = approval_callback

    def run(self, task, preferred=None):
        self.activity.emit("AGENT -> planning task")
        all_results = []
        current_task = task
        provider = preferred
        final_plan = {}
        completed = False

        for cycle in range(1, self.MAX_ITERATIONS + 1):
            plan, provider_name = self.router.plan(
                current_task,
                self._planner_system(),
                preferred=provider,
            )
            provider = provider_name
            final_plan = plan
            self.activity.emit(f"AGENT -> plan ready ({provider}) cycle {cycle}")

            steps = plan.get("steps")
            if not isinstance(steps, list):
                raise ValueError("Agent plan is missing a steps list.")
            if len(steps) > self.MAX_STEPS:
                raise ValueError(f"Agent plan has too many steps (max {self.MAX_STEPS}).")

            cycle_results = []
            for index, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    cycle_results.append({"cycle": cycle, "step": index, "error": "Invalid step object."})
                    continue

                tool = step.get("tool")
                args = step.get("args") or {}
                self.activity.emit(f"AGENT -> step {index}/{len(steps)}: {tool}")

                validation_error = self._validate_step(tool, args)
                if validation_error:
                    entry = {
                        "cycle": cycle,
                        "step": index,
                        "tool": tool,
                        "error": validation_error,
                    }
                    cycle_results.append(entry)
                    self.activity.emit(
                        f"AGENT BLOCKED/FAILED -> {tool}: {validation_error}"
                    )
                    continue

                try:
                    result = self._execute(tool, args)
                    entry = {"cycle": cycle, "step": index, "tool": tool, "result": result}
                    cycle_results.append(entry)
                    self.activity.emit(f"AGENT OK -> {tool}")
                except Exception as exc:
                    error = str(exc)
                    entry = {"cycle": cycle, "step": index, "tool": tool, "error": error}
                    cycle_results.append(entry)
                    self.activity.emit(f"AGENT BLOCKED/FAILED -> {tool}: {error}")

            all_results.extend(cycle_results)
            failure = self._find_failure(cycle_results)
            if not failure:
                completed = True
                break

            if cycle >= self.MAX_ITERATIONS:
                self.activity.emit("AGENT -> max recovery cycles reached")
                break

            self.activity.emit(f"AGENT -> recovering from cycle {cycle} failure")
            current_task = f"""Original task:
{task}

The previous agent cycle failed because of a tool execution or plan-validation problem.
Previous cycle results:
{json.dumps(cycle_results, ensure_ascii=False)}

Create a corrected minimal plan for the original task.
Use the exact required arguments for every tool.
Do not repeat a malformed or failed action unless you have fixed its cause.
Inspect relevant files when that is useful.
"""

        summary = self._summarize(
            task, final_plan, all_results, preferred=provider, completed=completed
        )
        if completed:
            self.activity.emit("AGENT -> task complete")
        else:
            self.activity.emit("AGENT -> task ended with failures")
        return summary, all_results

    def _validate_step(self, tool, args):
        if tool not in {
            "project_context",
            "list_workspace", "read_file", "write_file", "patch_file",
            "run_command", "run_tests", "git_status", "git_diff", "git_log", "git_branch",
        }:
            return f"Unknown planner tool: {tool}"

        if not isinstance(args, dict):
            return f"{tool} requires an args object."

        required = {
            "read_file": ("path",),
            "write_file": ("path", "content"),
            "patch_file": ("path", "old_text", "new_text"),
            "run_command": ("command",),
            "run_tests": (),
        }
        for key in required.get(tool, ()):
            if key not in args:
                return f"{tool} requires '{key}'."
            if not isinstance(args[key], str):
                return f"{tool} requires '{key}' to be a string."
            if key != "content" and not args[key].strip():
                return f"{tool} requires a non-empty '{key}'."

        if tool == "patch_file":
            expected = args.get("expected_replacements", 1)
            if not isinstance(expected, int) or expected < 1:
                return "patch_file requires expected_replacements to be a positive integer."

        if tool == "git_diff" and "paths" in args:
            paths = args["paths"]
            if not isinstance(paths, list) or not all(
                isinstance(path, str) and path.strip() for path in paths
            ):
                return "git_diff paths must be a list of non-empty strings."

        return None

    def _find_failure(self, results):
        for entry in results:
            if "error" in entry:
                return entry
            result = entry.get("result")
            if isinstance(result, dict) and result.get("exit_code", 0) != 0:
                return entry
        return None

    def _execute(self, tool, args):
        if tool == "git_commit":
            message = args.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("git_commit requires a commit message.")
            if not self._request_approval("git_commit", f"Create Git commit: {message}"):
                raise PermissionError("Git commit denied by user.")
            return self._git_commit(message)

        if tool == "project_context":
            return self.workspace.project_context()

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

        if tool == "patch_file":
            path = args.get("path")
            old_text = args.get("old_text")
            new_text = args.get("new_text")
            expected = args.get("expected_replacements", 1)
            if not isinstance(path, str) or not path.strip():
                raise ValueError("patch_file requires a path.")
            target, count = self.workspace.patch_file(path, old_text, new_text, expected)
            return f"Patched {target.relative_to(self.workspace.root)} ({count} replacement)."

        if tool == "git_status":
            return self._git("status", "--short")

        if tool == "git_diff":
            return self._git("diff", "--no-ext-diff", "--", *self._git_paths(args.get("paths")))

        if tool == "git_log":
            return self._git("log", "-5", "--oneline")

        if tool == "git_branch":
            return self._git("branch", "--show-current")

        if tool == "run_tests":
            command = args.get("command", "")
            if command and not isinstance(command, str):
                raise ValueError("run_tests command must be a string.")
            if not command.strip():
                command = "python -m unittest discover -v"
            code, output = run_command(command, self.activity, cwd=self.workspace.root)
            return {
                "action": "run_tests",
                "exit_code": code,
                "output": output[-self.MAX_RESULT_CHARS:],
            }

        if tool == "run_command":
            command = args.get("command")
            if not isinstance(command, str) or not command.strip():
                raise ValueError("run_command requires a command.")
            risky = any(re.search(pattern, command.lower()) for pattern in RISKY_PATTERNS)
            approved = False
            if risky:
                approved = self._request_approval("terminal", f"Run risky command: {command}")
                if not approved:
                    raise PermissionError("Risky command denied by user.")
            code, output = run_command(command, self.activity, approved=approved, cwd=self.workspace.root)
            return {
                "action": "run_command",
                "exit_code": code,
                "output": output[-self.MAX_RESULT_CHARS:],
            }

        raise ValueError(f"Unknown agent tool: {tool}")

    def _git_paths(self, paths):
        if paths is None:
            return []
        if not isinstance(paths, list) or not all(isinstance(path, str) and path.strip() for path in paths):
            raise ValueError("Git paths must be a list of relative path strings.")
        return paths

    def _request_approval(self, action, detail):
        if self.approval_callback is None:
            return False
        return bool(self.approval_callback(action, detail))

    def _git_commit(self, message):
        add = subprocess.run(
            ["git", "add", "-A"],
            cwd=str(self.workspace.root),
            capture_output=True,
            text=True,
            timeout=self.GIT_TIMEOUT,
            shell=False,
        )
        if add.returncode != 0:
            return {"exit_code": add.returncode, "output": (add.stdout or "") + (add.stderr or "")}
        return self._git("commit", "-m", message)

    def _git(self, *args):
        command = ["git", *args]
        for arg in args:
            if arg.startswith("/") or ":" in arg[:3]:
                raise ValueError("Git tool accepts repository-relative arguments only.")
        process = subprocess.run(
            command,
            cwd=str(self.workspace.root),
            capture_output=True,
            text=True,
            timeout=self.GIT_TIMEOUT,
            shell=False,
        )
        output = (process.stdout or "") + (("\n" + process.stderr) if process.stderr else "")
        return {"exit_code": process.returncode, "output": output[-self.MAX_RESULT_CHARS:]}

    def _planner_system(self):
        return """You are the planning component of Hariom AI, a local Windows workstation agent.
Understand natural-language requests yourself. The user may be brief, informal, or in Hinglish.
Infer the intended filename, implementation, tests, and minimal execution steps from the request.

Return ONLY valid JSON matching this exact shape:
{
  "steps": [
    {"tool": "project_context|list_workspace|read_file|write_file|patch_file|run_command|run_tests|git_status|git_diff|git_log|git_branch", "args": {}}
  ],
  "goal": "short description"
}

Tool argument requirements:
- project_context: {}
- read_file: {"path": "..."}
- write_file: {"path": "...", "content": "..."}
- patch_file: {"path": "...", "old_text": "...", "new_text": "...", "expected_replacements": 1}
- run_command: {"command": "..."}
- run_tests: {"command": "..."} or {} (defaults to python -m unittest discover -v)
- git_diff: {"paths": ["relative/path"]} or {"paths": []}

Rules:
- Use only the eleven listed tools.
- Paths for read_file/write_file/patch_file are relative to the user's workspace.
- Never use absolute paths.
- Infer missing details when the user's intent is clear. Do not ask the user for a filename when a sensible filename can be derived from the request.
- For coding tasks, use project_context first when project structure, framework, Git state, or development environment may matter.
- Use list_workspace/read_file when specific existing content is needed.
- Use write_file for creating new files or replacing complete files when appropriate.
- Use patch_file for targeted edits to existing files; include exact old_text and new_text.
- expected_replacements defaults to 1; set it explicitly when more than one identical occurrence is intentionally changed.
- Use run_tests for test suites; use run_command for other commands/builds only when needed.
- If a test command fails, inspect the failure and use the recovery cycle to make a corrected plan.
- Git tools are read-only in this version. Do not attempt git commit, push, merge, reset, clean, or other destructive Git operations.
- Keep the plan to the minimum steps needed.
- Never claim a tool ran; only describe intended steps.
"""

    def _summarize(self, task, plan, results, preferred=None, completed=False):
        compact = json.dumps(results, ensure_ascii=False)
        status = "completed successfully" if completed else "ended with failures or blocked actions"
        prompt = f"""Task:
{task}

Planned steps:
{json.dumps(plan, ensure_ascii=False)}

Actual tool results:
{compact}

Overall execution status:
{status}

Give a concise factual completion report.
Separate:
1. What was done
2. Files changed (if any)
3. Commands/tests run and their exit codes
4. Anything blocked, failed, or still needing approval
Never claim an action happened unless it appears in the actual tool results."""
        text, _ = self.router.chat(
            prompt,
            system="You are the reporting component of Hariom AI. Report only verified tool results.",
            preferred=preferred,
        )
        return text
