"""LLM-facing task planning boundary.

Model output is treated as untrusted data: only validated structured plans
may reach the execution layer.
"""
from typing import Any

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

        for action in plan.actions:
            try:
                self.tool_registry.validate_arguments(action.tool, action.arguments)
            except Exception as exc:
                raise AgentPlanningError(
                    f"Invalid arguments for tool '{action.tool}': {exc}"
                ) from exc
        return plan

    def parse_json(self, model_output: Any) -> TaskPlan:
        import json
        if not isinstance(model_output, str):
            raise AgentPlanningError("Model JSON output must be a string.")
        try:
            payload = json.loads(model_output)
        except json.JSONDecodeError as exc:
            raise AgentPlanningError(f"Invalid model JSON: {exc.msg}") from exc
        return self.parse(payload)
