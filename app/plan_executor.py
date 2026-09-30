"""Plan-to-approval execution facade with observable state."""
from .approval_workflow import ApprovalWorkflow
from .execution_state import ExecutionState
from .recovery import RecoveryCoordinator
from .task_executor import TaskAction, TaskExecutionError
from .task_plan import TaskPlan\nfrom .task_service import TaskService, TaskServiceError


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
            self.task_service.transition(task_id, "awaiting_approval", request_id=result.get("request_id"))\n            state.transition("approval", request_id=result.get("request_id"))
        else:
            self.task_service.transition(task_id, "failed", error_type=result.get("stage"))\n            state.transition("failed", error_type=result.get("stage"))
        state.result = dict(result)
        result["plan"] = plan.to_dict()
        result["state"] = state.snapshot()
        return result

    def recover(self, task_id, repair_actions, test_target=None):
        state = self._states.get(task_id)
        if state is None:
            raise PlanExecutionError(f"Unknown task: {task_id}")
        if not isinstance(repair_actions, (list, tuple)) or not repair_actions:
            raise PlanExecutionError("Repair actions are required.")
        actions = tuple(repair_actions)
        if not all(isinstance(action, TaskAction) for action in actions):
            raise PlanExecutionError("Repair actions must be TaskAction objects.")
        target = test_target or state.result.get("test_target") or "tests"

        def verify():
            result = self.workflow.executor.registry.test_runner.run(target)
            state.result = dict(result)
            return result

        def repair(_failure):
            if not state.record_attempt():
                return {"ok": False, "stage": "recovery_limit"}
            state.transition("repairing", attempt=state.attempts)
            try:
                result = self.workflow.executor.execute(actions)
            except TaskExecutionError as exc:
                state.transition("failed", error_type="repair_execution")
                return {"ok": False, "stage": "repair_execution", "error": str(exc)}
            if not result.get("ok"):
                state.transition("failed", error_type="repair_execution")
                return result
            return {"ok": True, "execution": result}

        state.transition("recovering", max_attempts=state.max_attempts)
        recovery = RecoveryCoordinator(
            verify,
            repair,
            max_attempts=state.max_attempts,
        ).run()
        if recovery.ok:
            state.transition("approval", recovered=True)
        else:
            state.transition("failed", error_type=recovery.final_result.get("stage"))
        state.result = dict(recovery.final_result)
        return {
            "ok": recovery.ok,
            "stage": "approval" if recovery.ok else "recovery",
            "attempts": recovery.attempts,
            "state": state.snapshot(),
            "result": recovery.final_result,
        }

    def approve(self, request_id, message):
        result = self.workflow.approve(request_id, message)
        for state in self._states.values():
            if state.result.get("request_id") == request_id:
                self.task_service.transition(state.task_id, "completed", request_id=request_id)\n                state.transition("committed")
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
