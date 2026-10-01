import json
import re

from .context import WorkspaceContext
from .memory import MemoryStore
from .skills import SkillRegistry
from .task_engine import TaskState, TaskStatus, TaskCheckpointStore
from .config import APP_DIR
from .tools import ToolRegistry
from .verification import Verifier


SYSTEM_PROMPT = """You are Hariom AI, a personal computer/workspace assistant.
Plan practical work, use explicit tools, observe results, recover from failures, and verify outcomes.
Never claim a tool action happened unless its result and verification support that claim.
Prefer small observable steps. Protected actions require approval.
Use relevant skills and workspace context, but do not invent facts."""


class PersonalAgent:
    """Recoverable plan -> execute -> observe -> repair -> verify agent."""

    def __init__(self, router, workspace, activity, memory=None, tools=None, skills=None):
        self.router = router
        self.workspace = workspace
        self.activity = activity
        self.memory = memory or MemoryStore()
        self.tools = tools or ToolRegistry(workspace, activity)
        self.skills = skills or SkillRegistry(workspace.root / "skills")
        self.verifier = Verifier()
        self.checkpoints = TaskCheckpointStore(APP_DIR / "tasks")

    def context(self, request):
        return {
            "memory": self.memory.search(request, limit=8),
            "recent_memory": self.memory.recent(limit=5),
            "workspace": WorkspaceContext(self.workspace).snapshot(),
            "tools": self.tools.describe(),
            "skills": self.skills.catalog(),
            "selected_skill_instructions": self.skills.instructions_for(request),
        }

    def plan(self, request):
        ctx = self.context(request)
        prompt = (
            "Create a practical execution plan. Return JSON only with an array named steps. "
            "Each step has description, optional tool and optional arguments. "
            "Only use tools from the supplied tool list. "
            "Do not claim execution or invent results.\n\nREQUEST:\n" + request +
            "\n\nCONTEXT:\n" + json.dumps(ctx, ensure_ascii=False)
        )
        message, provider = self.router.chat_messages(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": prompt}],
            profile="hariom/reasoning",
            response_format={"type": "json_object"},
        )
        data = self._parse_json(message.get("content", ""))
        state = TaskState(request=request)
        steps = data.get("steps") if isinstance(data, dict) else None
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict):
                    state.add_step(
                        str(step.get("description", "Unnamed step")),
                        step.get("tool"),
                        step.get("arguments") or {},
                    )
        if not state.steps:
            state.add_step(message.get("content", "Plan unavailable"))
        self.activity.emit("AGENT PLAN -> %s step(s) via %s" % (len(state.steps), provider))
        return state

    def execute(self, state, approve=False, max_attempts=2):
        was_waiting = state.status == TaskStatus.WAITING_APPROVAL
        state.status = TaskStatus.RUNNING
        start = state.current_step if was_waiting else 0

        for index in range(start, len(state.steps)):
            step = state.steps[index]
            if step.get("status") == "completed":
                continue
            state.start_step(index)
            tool_name = step.get("tool")

            if not tool_name:
                state.finish_step(step["description"])
                continue

            try:
                tool = self.tools.get(tool_name)
                if not tool:
                    raise KeyError("Unknown tool: " + str(tool_name))
                if tool.requires_approval and not approve:
                    state.status = TaskStatus.WAITING_APPROVAL
                    self.activity.emit("AGENT -> approval required for " + tool_name)
                    return state

                output = self.tools.execute(tool_name, step.get("arguments"), approved=approve)
                step["workspace_root"] = str(self.workspace.root)
                state.finish_step(str(output)[-12000:])
            except Exception as exc:
                state.fail_step(exc)
                state.attempts += 1
                self.activity.emit("AGENT FAILED -> %s: %s" % (tool_name, exc))
                if state.attempts >= max_attempts:
                    state.status = TaskStatus.FAILED
                    state.result = "Task stopped after bounded recovery attempts."
                    return state
                if self.repair(state, index, str(exc)):
                    state.status = TaskStatus.RUNNING
                    continue
                state.status = TaskStatus.FAILED
                state.result = "Task could not be repaired safely."
                return state

        state.status = TaskStatus.VERIFYING
        ok, failures = self.verifier.verify_task(state)
        if ok:
            state.status = TaskStatus.COMPLETED
            state.result = "Task completed and verified."
        else:
            state.status = TaskStatus.FAILED
            state.errors.extend(failures)
            state.result = "Task execution finished, but verification failed: " + "; ".join(failures)
        return state

    def repair(self, state, failed_index, error):
        step = state.steps[failed_index]
        prompt = (
            "A task step failed. Return JSON only with a replacement object named step. "
            "The replacement must use an existing tool or null. Keep the repair minimal and safe. "
            "Do not pretend the failed action succeeded.\n\n"
            "REQUEST:\n" + state.request +
            "\nFAILED STEP:\n" + json.dumps(step, ensure_ascii=False) +
            "\nERROR:\n" + error +
            "\nTOOLS:\n" + json.dumps(self.tools.describe(), ensure_ascii=False)
        )
        try:
            message, provider = self.router.chat_messages(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content": prompt}],
                profile="hariom/reasoning",
                response_format={"type": "json_object"},
            )
            data = self._parse_json(message.get("content", ""))
            replacement = data.get("step") if isinstance(data, dict) else None
            if not isinstance(replacement, dict):
                return False
            step.update({
                "description": str(replacement.get("description", step["description"])),
                "tool": replacement.get("tool"),
                "arguments": replacement.get("arguments") or {},
                "status": "pending",
                "output": "",
            })
            self.activity.emit("AGENT REPAIR -> step %s via %s" % (failed_index + 1, provider))
            return True
        except Exception as exc:
            self.activity.emit("AGENT REPAIR FAILED -> " + str(exc))
            return False

    def run(self, request, approve=False):
        state = self.plan(request)
        self._checkpoint(state)
        return self.execute(state, approve=approve)

    def resume(self, task_id, approve=False):
        state = self.checkpoints.load(task_id)
        if state is None:
            raise KeyError("No saved task: " + str(task_id))
        self.activity.emit("AGENT RESUME -> " + str(task_id))
        state = self.execute(state, approve=approve)
        self._checkpoint(state)
        return state

    def _checkpoint(self, state):
        self.checkpoints.save(self.task_id(state), state)

    @staticmethod
    def task_id(state):
        return "task-" + str(int(state.created_at * 1000))

    @staticmethod
    def _parse_json(content):
        try:
            return json.loads(content)
        except (TypeError, ValueError):
            match = re.search(r"\{.*\}", content or "", re.S)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except (TypeError, ValueError):
                return {}

class Agent(PersonalAgent):
    """Backward-compatible adapter for the legacy Agent test/tool surface.

    The active workstation path remains AgentRunner/TaskAPI; this adapter only
    preserves the older local test contract without changing that execution path.
    """

    def __init__(self, router, workspace, activity, approval_callback=None):
        self.router = router
        self.workspace = workspace
        self.activity = activity
        self.approval_callback = approval_callback
        self.tools = ToolRegistry(workspace, activity)
        self.verifier = Verifier()
        self._legacy_results = []

    def _execute(self, action, arguments=None):
        arguments = arguments or {}
        if action == "project_context":
            import subprocess
            files = self.workspace.list_files()
            extensions = {}
            for path in files:
                extensions[path.suffix.lower()] = extensions.get(path.suffix.lower(), 0) + 1
            manifests = [path.name for path in files if path.name in {"requirements.txt", "pyproject.toml", "package.json"}]
            branch = subprocess.run(["git", "branch", "--show-current"], cwd=self.workspace.root, capture_output=True, text=True)
            status = subprocess.run(["git", "status", "--short"], cwd=self.workspace.root, capture_output=True, text=True)
            return {
                "workspace": str(self.workspace.root),
                "file_count": len(files),
                "manifests": manifests,
                "extensions": extensions,
                "windows": __import__("os").name == "nt",
                "vscode_running": False,
                "git_branch": branch.stdout.strip(),
                "git_status": status.stdout.strip(),
            }
        if action == "git_branch":
            import subprocess
            result = subprocess.run(["git", "branch", "--show-current"], cwd=self.workspace.root, capture_output=True, text=True)
            return {"action": action, "exit_code": result.returncode, "output": result.stdout.strip()}
        if action == "git_commit":
            if self.approval_callback is not None and not self.approval_callback(action, arguments):
                raise PermissionError("Approval required for tool: git_commit")
            elif self.approval_callback is None:
                raise PermissionError("Approval required for tool: git_commit")
            import subprocess
            result = subprocess.run(["git", "add", "."], cwd=self.workspace.root, capture_output=True, text=True)
            if result.returncode == 0:
                result = subprocess.run(["git", "commit", "-m", str(arguments.get("message", ""))], cwd=self.workspace.root, capture_output=True, text=True)
            return {"action": action, "exit_code": result.returncode, "output": (result.stdout + result.stderr)[-4000:]}
        tool_map = {"write_file": "write_file", "run_command": "run_command", "read_file": "read_file", "list_files": "list_files"}
        name = tool_map.get(action, action)
        result = self.tools.execute(name, arguments, approved=True)
        return {"action": action, "exit_code": 0, "output": result}

    def run(self, request):
        summary, results = self._plan_and_execute(request)
        return summary, results

    def _plan_and_execute(self, request):
        results = []
        for cycle in range(3):
            plan, _provider = self.router.plan(request, "", preferred="hariom/reasoning")
            steps = plan.get("steps", []) if isinstance(plan, dict) else []
            cycle_failed = False
            for step in steps:
                tool = step.get("tool")
                args = step.get("args") or {}
                try:
                    results.append({"result": self._execute(tool, args)})
                except Exception as exc:
                    results.append({"error": str(exc), "tool": tool})
                    self.activity.emit("recovering from cycle %s failure" % (cycle + 1))
                    cycle_failed = True
                    break
            if not cycle_failed:
                summary, _ = self.router.chat(request, preferred="hariom/reasoning")
                return summary, results
        return "Task could not be repaired safely.", results
