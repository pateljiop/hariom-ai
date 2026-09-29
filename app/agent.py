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
            self._checkpoint(state)
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
                    self._checkpoint(state)
                    return state

                output = self.tools.execute(tool_name, step.get("arguments"), approved=approve)
                step["workspace_root"] = str(self.workspace.root)
                state.finish_step(str(output)[-12000:])
                self._checkpoint(state)
            except Exception as exc:
                state.fail_step(exc)
                state.attempts += 1
                self.activity.emit("AGENT FAILED -> %s: %s" % (tool_name, exc))
                if state.attempts >= max_attempts:
                    state.status = TaskStatus.FAILED
                    state.result = "Task stopped after bounded recovery attempts."
                    self._checkpoint(state)
                    return state
                if self.repair(state, index, str(exc)):
                    state.status = TaskStatus.RUNNING
                    self._checkpoint(state)
                    continue
                state.status = TaskStatus.FAILED
                state.result = "Task could not be repaired safely."
                self._checkpoint(state)
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
        self._checkpoint(state)
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
