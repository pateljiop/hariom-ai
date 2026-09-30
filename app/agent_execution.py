"""Validated model-plan execution facade."""
from .agent_planner import AgentPlanner
from .plan_executor import PlanExecutor


class AgentExecutionError(Exception):
    """Raised when model output cannot safely enter execution."""


class AgentExecutionFacade:
    def __init__(self, tool_registry=None, executor=None):
        if executor is None:
            executor = PlanExecutor()
        self.executor = executor
        registry = tool_registry or executor.workflow.executor.registry
        self.planner = AgentPlanner(registry)

    def prepare_model_output(self, model_output, task_id=None):
        try:
            plan = self.planner.parse(model_output)
        except Exception as exc:
            raise AgentExecutionError(str(exc)) from exc
        return self.executor.prepare(plan.to_dict(), task_id=task_id)

    def prepare_model_json(self, model_output, task_id=None):
        try:
            plan = self.planner.parse_json(model_output)
        except Exception as exc:
            raise AgentExecutionError(str(exc)) from exc
        return self.executor.prepare(plan.to_dict(), task_id=task_id)

    def approve(self, request_id, message):
        return self.executor.approve(request_id, message)

    def get_state(self, task_id):
        return self.executor.get_state(task_id)
