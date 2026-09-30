"""Plan-to-approval execution facade for the agent."""
from .approval_workflow import ApprovalWorkflow
from .task_plan import TaskPlan


class PlanExecutionError(Exception):
    """Base error for plan execution failures."""


class PlanExecutor:
    def __init__(self, workflow=None):
        self.workflow = workflow or ApprovalWorkflow()

    def prepare(self, payload):
        plan = TaskPlan.from_dict(payload)
        result = self.workflow.prepare(plan.actions, plan.test_target)
        if result.get("ok"):
            result["plan"] = plan.to_dict()
        return result

    def approve(self, request_id, message):
        return self.workflow.approve(request_id, message)
