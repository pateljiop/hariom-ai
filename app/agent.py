import json
import re
from .memory import MemoryStore
from .task_engine import TaskState, TaskStatus
from .tools import ToolRegistry

SYSTEM_PROMPT = """You are Hariom AI, a personal computer/workspace assistant.
Help the owner plan, execute and verify practical tasks.
Never claim a tool action happened unless the tool result confirms it.
Prefer small verifiable steps. Ask for approval before destructive or externally consequential actions."""

class PersonalAgent:
    """Planner/executor/verifier shell around the existing multi-provider router."""
    def __init__(self, router, workspace, activity, memory=None, tools=None):
        self.router = router
        self.workspace = workspace
        self.activity = activity
        self.memory = memory or MemoryStore()
        self.tools = tools or ToolRegistry(workspace, activity)

    def context(self, request):
        return {"memories":self.memory.search(request,limit=6),"workspace":self.tools.list_files(limit=80),"tools":self.tools.describe()}

    def plan(self, request):
        ctx = self.context(request)
        prompt = ("Create a practical execution plan for this user request. Return JSON only with an array named steps. "
                  "Each step needs description, optional tool and optional arguments. Only choose tools from the supplied tool list. "
                  "Do not invent tool results.\n\nREQUEST:\n" + request +
                  "\n\nCONTEXT:\n" + json.dumps(ctx,ensure_ascii=False))
        message, provider = self.router.chat_messages(
            [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":prompt}],
            profile="hariom/reasoning", response_format={"type":"json_object"})
        data = self._parse_json(message.get("content",""))
        steps = data.get("steps") if isinstance(data,dict) else None
        state = TaskState(request=request)
        if isinstance(steps,list):
            for step in steps:
                if isinstance(step,dict):
                    state.add_step(str(step.get("description","Unnamed step")),step.get("tool"),step.get("arguments") or {})
        if not state.steps:
            state.add_step(message.get("content","Plan unavailable"))
        self.activity.emit("AGENT PLAN -> %s step(s) via %s" % (len(state.steps),provider))
        return state

    def execute(self, state, approve=False):
        state.status = TaskStatus.RUNNING
        for index, step in enumerate(state.steps):
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
                output = self.tools.execute(tool_name,step.get("arguments"),approved=approve)
                state.finish_step(str(output)[-12000:])
            except Exception as exc:
                state.fail_step(exc)
                state.status = TaskStatus.FAILED
                self.activity.emit("AGENT FAILED -> %s: %s" % (tool_name,exc))
                return state
        state.status = TaskStatus.VERIFYING
        if self.verify(state):
            state.status = TaskStatus.COMPLETED
            state.result = "Task completed and verified."
        else:
            state.status = TaskStatus.FAILED
            state.result = "Task execution finished, but verification failed."
        return state

    def verify(self, state):
        for step in state.steps:
            if step["status"] != "completed":
                return False
            if step.get("tool") and not step.get("output"):
                return False
        return True

    def run(self, request, approve=False):
        return self.execute(self.plan(request),approve=approve)

    @staticmethod
    def _parse_json(content):
        try:
            return json.loads(content)
        except (TypeError,ValueError):
            match = re.search(r"\{.*\}",content or "",re.S)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except (TypeError,ValueError):
                return {}
