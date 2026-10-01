"""Agent-facing application API for Phase 1 task lifecycle operations.

This layer intentionally stays framework-neutral. A future HTTP adapter can map
these methods directly to POST/GET endpoints without duplicating execution logic.
"""

from .agent_planner import AgentPlanner, AgentPlanningError
from .approval_workflow import ApprovalWorkflow, ApprovalWorkflowError
from .plan_executor import PlanExecutor, PlanExecutionError
from .task_plan import PlanValidationError, TaskPlan
from .task_service import TaskNotFoundError, TaskService, TaskServiceError


class TaskAPIError(Exception):
    """Base error exposed by the task API."""


class TaskAPI:
    ENDPOINTS = {
        "POST /tasks": "create_task",
        "GET /tasks/{task_id}": "get_task",
        "POST /tasks/{task_id}/validate": "validate_task",
        "POST /tasks/{task_id}/preview": "preview_task",
        "POST /tasks/{task_id}/execute": "execute_task",
        "POST /tasks/{task_id}/cancel": "cancel_task",
        "POST /tasks/{task_id}/approve": "approve_task",
        "POST /tasks/{task_id}/reject": "reject_task",
        "GET /tasks/{task_id}/events": "get_events",
        "GET /tasks/{task_id}/diff": "get_diff",
    }

    def __init__(self, task_service=None, executor=None, workflow=None, tool_registry=None):
        self.task_service = task_service or TaskService()
        self.executor = executor or PlanExecutor(task_service=self.task_service, workflow=workflow)
        self.workflow = workflow or self.executor.workflow
        self.tool_registry = tool_registry or self.workflow.executor.registry
        self.planner = AgentPlanner(self.tool_registry)

    def create_task(self, payload):
        payload = self._object(payload)
        request = payload.get("user_request")
        objective = payload.get("objective") or request
        if not isinstance(request, str) or not request.strip():
            raise TaskAPIError("user_request must be a non-empty string.")
        if not isinstance(objective, str) or not objective.strip():
            raise TaskAPIError("objective must be a non-empty string.")

        task_id = payload.get("task_id")
        plan_payload = payload.get("plan")
        plan = None
        fields = {}
        if plan_payload is not None:
            plan = self._validate_payload(plan_payload)
            if task_id and plan.task_id and plan.task_id != task_id:
                raise TaskAPIError("task_id does not match plan.task_id.")
            task_id = task_id or plan.task_id or None
            fields = {
                "steps": tuple(plan.steps),
                "dependencies": tuple(plan.dependencies),
                "expected_files": tuple(plan.expected_files),
                "test_commands": tuple(plan.test_commands),
                "risk_level": plan.risk_level,
                "required_approvals": tuple(plan.required_approvals),
                "rollback_strategy": plan.rollback_strategy,
                "max_retries": plan.max_retries,
                "plan": plan.to_dict(),
            }

        task = self.task_service.create_task(
            request,
            objective=objective,
            task_id=task_id,
            **fields,
        )
        return self._task_response(task)

    def get_task(self, task_id):
        return self._task_response(self.task_service.get_task(task_id))

    def validate_task(self, task_id, payload=None):
        task = self.task_service.get_task(task_id)
        source = payload if payload is not None else task.plan
        if source is None:
            raise TaskAPIError("A TaskPlan payload is required for validation.")
        plan = self._validate_payload(source)
        if plan.task_id and plan.task_id != task_id:
            raise TaskAPIError("Plan task_id does not match requested task.")
        return self._validation_response(task_id, plan)

    def preview_task(self, task_id, payload=None):
        result = self.validate_task(task_id, payload)
        plan = TaskPlan.from_dict(result["plan"])
        actions = []
        for action in plan.actions:
            spec = next(item for item in self.tool_registry.describe() if item["name"] == action.tool)
            permission = spec.get("permission")
            decision = None
            if permission:
                decision = self.tool_registry.permission_manager.decide(permission, approved=False)
            needs_approval = bool(
                spec.get("requires_approval")
                or spec.get("risk") in {"high", "critical"}
                or (decision is not None and not decision.allowed)
            )
            actions.append({
                "step_id": action.step_id,
                "tool": action.tool,
                "arguments": dict(action.arguments),
                "risk": spec.get("risk", "low"),
                "permission": permission,
                "requires_approval": needs_approval,
                "timeout": spec.get("timeout"),
                "retry": spec.get("retry"),
                "rollback": spec.get("rollback"),
            })
        return {
            "ok": True,
            "task_id": task_id,
            "plan": plan.to_dict(),
            "actions": actions,
            "risk_level": plan.risk_level,
            "required_approvals": list(plan.required_approvals),
            "approval_required": any(item["requires_approval"] for item in actions),
        }

    def execute_task(self, task_id, payload=None):
        task = self.task_service.get_task(task_id)
        source = payload if payload is not None else task.plan
        if source is None:
            raise TaskAPIError("A TaskPlan payload is required for execution.")
        plan = self._validate_payload(source)
        if plan.task_id and plan.task_id != task_id:
            raise TaskAPIError("Plan task_id does not match requested task.")
        if not plan.task_id:
            source = dict(source)
            source["task_id"] = task_id
        return self.executor.prepare(source, task_id=task_id)

    def cancel_task(self, task_id, reason="cancelled by user"):
        return self._task_response(self.task_service.cancel_task(task_id, reason))

    def approve_task(self, task_id, request_id, message):
        task = self.task_service.get_task(task_id)
        approval = self.task_service.store.get_approval(request_id)
        if approval is None:
            raise TaskAPIError(f"Unknown approval request: {request_id}")
        if approval.get("task_id") != task_id:
            raise TaskAPIError("Approval request does not belong to this task.")
        return self.executor.approve(request_id, message)

    def reject_task(self, task_id, request_id, reason="rejected by user"):
        self.task_service.get_task(task_id)
        approval = self.task_service.store.get_approval(request_id)
        if approval is None:
            raise TaskAPIError(f"Unknown approval request: {request_id}")
        if approval.get("task_id") != task_id:
            raise TaskAPIError("Approval request does not belong to this task.")
        return self.workflow.reject(request_id, reason)

    def get_events(self, task_id):
        return {"task_id": task_id, "events": self.task_service.events(task_id)}

    def get_diff(self, task_id):
        task = self.task_service.get_task(task_id)
        request_id = task.result.get("request_id") if isinstance(task.result, dict) else None
        diff = ""
        if request_id:
            approval = self.task_service.store.get_approval(request_id)
            if approval:
                diff = approval.get("diff", "")
        if not diff and isinstance(task.result, dict):
            diff = task.result.get("diff", "")
        return {"task_id": task_id, "diff": diff}

    def _validate_payload(self, payload):
        try:
            return self.planner.parse(payload)
        except (PlanValidationError, AgentPlanningError) as exc:
            raise TaskAPIError(str(exc)) from exc

    @staticmethod
    def _object(payload):
        if not isinstance(payload, dict):
            raise TaskAPIError("Request body must be an object.")
        return payload

    @staticmethod
    def _task_response(task):
        return {"ok": True, "task": task.to_dict()}

    @staticmethod
    def _validation_response(task_id, plan):
        return {
            "ok": True,
            "task_id": task_id,
            "valid": True,
            "plan": plan.to_dict(),
        }
