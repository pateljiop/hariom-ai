"""Plan-to-approval execution facade with observable state."""
from .approval_workflow import ApprovalWorkflow
from .execution_state import ExecutionState
from .task_plan import TaskPlan


class PlanExecutionError(Exception):
    """Base error for plan execution failures."""


class PlanExecutor:
    def __init__(self, workflow=None):
        self.workflow = workflow or ApprovalWorkflow()
        self._states = {}

    def prepare(self, payload, task_id=None):
        plan = TaskPlan.from_dict(payload)
        task_id = task_id or self._make_task_id(plan)
        state = ExecutionState(task_id)
        self._states[task_id] = state
        state.transition("validated", action_count=len(plan.actions))
        state.transition("executing")
        result = self.workflow.prepare(plan.actions, plan.test_target)
        if result.get("ok"):
            state.transition("approval", request_id=result.get("request_id"))
        else:
            state.transition("failed", error_type=result.get("stage"))
        state.result = dict(result)
        result["plan"] = plan.to_dict()
        result["state"] = state.snapshot()
        return result

    def approve(self, request_id, message):
        result = self.workflow.approve(request_id, message)
        for state in self._states.values():
            if state.result.get("request_id") == request_id:
                state.transition("committed")
                state.result = dict(result)
                result["state"] = state.snapshot()
                break
        return result

    def get_state(self, task_id):
        state = self._states.get(task_id)
        if state is None:
            raise PlanExecutionError(f"Unknown task: {task_id}")
        return state.snapshot()

    @staticmethod
    def _make_task_id(plan):
        import hashlib
        return hashlib.sha256(repr(plan).encode("utf-8")).hexdigest()[:16]
