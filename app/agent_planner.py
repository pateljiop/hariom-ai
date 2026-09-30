"""LLM-facing task planning boundary.

Model output is treated as untrusted data: only validated structured plans
may reach the execution layer.
"""
from typing import Any, Dict

from .task_plan import TaskPlan, PlanValidationError


class AgentPlanningError(PlanValidationError):
    """Raised when model output cannot be converted into a safe plan."""


class AgentPlanner:
    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def tool_catalog(self):
        return self.tool_registry.describe()

    def parse(self, model_output: Any) -> TaskPlan:
        if isinstance(model_output, TaskPlan):
            plan = model_output
        elif isinstance(model_output, dict):
            plan = TaskPlan.from_dict(model_output)
        else:
            raise AgentPlanningError("Model output must be a structured plan object.")

        known = {item["name"] for item in self.tool_registry.describe()}
        for action in plan.actions:
            if action.tool not in known:
                raise AgentPlanningError(f"Unknown tool in plan: {action.tool}")
            schema = next(item["schema"] for item in self.tool_registry.describe() if item["name"] == action.tool)
            required = set(schema["required"])
            missing = required.difference(action.arguments)
            if missing:
                raise AgentPlanningError(
                    f"Tool '{action.tool}' is missing required arguments: {', '.join(sorted(missing))}"
                )
        return plan

    def parse_json(self, model_output: Any) -> TaskPlan:
        import json
        if not isinstance(model_output, str):
            raise AgentPlanningError("Model JSON output must be a string.")
        try:
            payload = json.loads(model_output)
        except json.JSONDecodeError as exc:
            raise AgentPlanningError(f"Invalid model JSON: {exc.msg}")
        return self.parse(payload)
