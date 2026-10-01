"""Plan-to-approval execution facade with observable state."""
from .approval_workflow import ApprovalWorkflow
from .execution_state import ExecutionState
from .recovery import RecoveryCoordinator
from .task_executor import TaskAction, TaskExecutionError
from .task_plan import TaskPlan
from .task_service import TaskService, TaskServiceError


class PlanExecutionError(Exception):
    """Base error for plan execution failures."""


class PlanExecutor:
    def __init__(self, workflow=None, task_service=None):
        self.task_service = task_service or TaskService()
        self.workflow = workflow or ApprovalWorkflow(store=self.task_service.store)
        self._states = {}

    def prepare(self, payload, task_id=None):
        plan = TaskPlan.from_dict(payload)
        requested_task_id = task_id or plan.task_id
        if requested_task_id:
            task_id = requested_task_id
            try:
                self.task_service.get_task(task_id)
            except TaskServiceError:
                self.task_service.create_task(
                    plan.user_request or "agent task",
                    objective=plan.objective or plan.user_request or "agent task",
                    task_id=task_id, steps=tuple(plan.steps),
                    dependencies=tuple(plan.dependencies),
                    expected_files=tuple(plan.expected_files),
                    test_commands=tuple(plan.test_commands),
                    risk_level=plan.risk_level,
                    required_approvals=tuple(plan.required_approvals),
                    rollback_strategy=plan.rollback_strategy,
                    max_retries=plan.max_retries,
                    plan=plan.to_dict(),
                )
        else:
            created = self.task_service.create_task(
                plan.user_request or "agent task",
                objective=plan.objective or plan.user_request or "agent task",
                dependencies=tuple(plan.dependencies),
                expected_files=tuple(plan.expected_files),
                test_commands=tuple(plan.test_commands),
                risk_level=plan.risk_level,
                required_approvals=tuple(plan.required_approvals),
                rollback_strategy=plan.rollback_strategy,
                max_retries=plan.max_retries,
                plan=plan.to_dict(),
            )
            task_id = created.task_id
        state = self._restore_state(task_id)
        if state is None:
            state = ExecutionState(task_id, max_attempts=plan.max_retries)
            self._states[task_id] = state
        else:
            state.max_attempts = plan.max_retries
        state.ensure_steps(plan.actions)
        self._persist_state(task_id, state)
        self.task_service.transition(task_id, "planning")
        self.task_service.transition(task_id, "validating")
        state.transition("validated", action_count=len(plan.actions))
        self._persist_state(task_id, state)
        self.task_service.transition(task_id, "executing")
        state.transition("executing")
        self._persist_state(task_id, state)

        def checkpoint():
            self._persist_state(task_id, state)

        result = self.workflow.prepare(
            plan.actions, plan.test_target, task_id=task_id,
            step_state=state.steps, checkpoint=checkpoint,
            max_step_retries=plan.max_retries,
            expected_files=plan.expected_files,
            test_commands=plan.test_commands,
        )
        if result.get("ok"):
            self.task_service.transition(task_id, "testing")
            self.task_service.transition(
                task_id, "awaiting_commit_approval", request_id=result.get("request_id")
            )
            state.transition("approval", request_id=result.get("request_id"))
        else:
            self.task_service.transition(task_id, "testing")
            self.task_service.transition(task_id, "failed", error_type=result.get("stage"))
            state.transition("failed", error_type=result.get("stage"))
        state.result = dict(result)
        result["plan"] = plan.to_dict()
        result["state"] = state.snapshot()
        self._persist_state(task_id, state)
        return result

    def recover(self, task_id, repair_actions, test_target=None):
        state = self._restore_state(task_id)
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
                result = self.workflow.executor.execute(actions, task_id=task_id)
            except TaskExecutionError as exc:
                state.transition("failed", error_type="repair_execution")
                return {"ok": False, "stage": "repair_execution", "error": str(exc)}
            if not result.get("ok"):
                state.transition("failed", error_type="repair_execution")
                return result
            return {"ok": True, "execution": result}

        state.transition("recovering", max_attempts=state.max_attempts)
        recovery = RecoveryCoordinator(verify, repair, max_attempts=state.max_attempts).run()
        if recovery.ok:
            state.transition("approval", recovered=True)
        else:
            state.transition("failed", error_type=recovery.final_result.get("stage"))
        state.result = dict(recovery.final_result)
        self._persist_state(task_id, state)
        return {
            "ok": recovery.ok,
            "stage": "approval" if recovery.ok else "recovery",
            "attempts": recovery.attempts,
            "state": state.snapshot(),
            "result": recovery.final_result,
        }

    def approve(self, request_id, message):
        result = self.workflow.approve(request_id, message)
        approval = self.task_service.store.get_approval(request_id)
        task_id = approval.get("task_id") if approval else None
        state = self._states.get(task_id) if task_id else None
        if state is None and task_id:
            state = self._restore_state(task_id)
        if state is None:
            for candidate in self._states.values():
                if candidate.result.get("request_id") == request_id:
                    state = candidate
                    task_id = candidate.task_id
                    break
        verification = result.get("post_commit_verification")
        if task_id:
            task = self.task_service.get_task(task_id)
            if task.status.value == "awaiting_commit_approval":
                self.task_service.transition(task_id, "committing", request_id=request_id)
                plan = TaskPlan.from_dict(task.plan or {})
                verification = self.workflow.executor.verify_expectations(
                    plan.expected_files, plan.test_commands
                )
                if verification.get("ok"):
                    verification["test_result"] = self.workflow.executor.registry.test_runner.run(
                        plan.test_target
                    )
                    verification["ok"] = bool(verification["test_result"].get("ok"))
                if not verification.get("ok"):
                    self.task_service.transition(
                        task_id, "failed", error_type="post_commit_verification"
                    )
                    if state is None:
                        state = ExecutionState(task_id, max_attempts=task.max_retries)
                        self._states[task_id] = state
                    commit = result.get("commit") or {}
                    rollback_candidate = {
                        "branch_name": commit.get("branch_name"),
                        "pre_commit_head": commit.get("pre_commit_head"),
                        "post_commit_head": commit.get("post_commit_head"),
                    }
                    state.result = {
                        "ok": False,
                        "stage": "post_commit_verification",
                        "commit": commit,
                        "verification": verification,
                        "rollback_candidate": rollback_candidate,
                    }
                    state.transition("failed", error_type="post_commit_verification")
                    self._persist_state(task_id, state)
                    result["ok"] = False
                    result["stage"] = "post_commit_verification"
                    result["state"] = state.snapshot()
                    result["verification"] = verification
                    return result
                self.task_service.transition(task_id, "completed", request_id=request_id)
            elif task.status.value != "completed":
                raise PlanExecutionError(
                    f"Task '{task_id}' is not awaiting commit approval."
                )
            if state is None:
                state = ExecutionState(task_id, max_attempts=task.max_retries)
                self._states[task_id] = state
            if state.stage != "committed":
                state.transition("committed")
            state.result = dict(result)
            state.result["post_commit_verification"] = verification
            self._persist_state(task_id, state)
            result["state"] = state.snapshot()
            result["post_commit_verification"] = verification
        return result

    def rollback(self, task_id, approved=False):
        """Explicitly compensate a failed post-commit task with a Git revert."""
        if not approved:
            raise PermissionError("Task rollback requires explicit human approval.")
        task = self.task_service.get_task(task_id)
        if task.status.value != "failed":
            raise PlanExecutionError(
                f"Task '{task_id}' can only be rolled back from failed status."
            )
        candidate = task.result.get("execution_state", {}).get("result", {}).get(
            "rollback_candidate"
        )
        if not isinstance(candidate, dict):
            candidate = task.result.get("rollback_candidate")
        if not isinstance(candidate, dict):
            raise PlanExecutionError("Task has no verified rollback candidate.")
        branch = candidate.get("branch_name")
        pre_commit = candidate.get("pre_commit_head")
        post_commit = candidate.get("post_commit_head")
        if not branch or not pre_commit or not post_commit:
            raise PlanExecutionError("Rollback candidate is incomplete.")
        if self.workflow.git.current_branch() != branch:
            raise PlanExecutionError("Git branch changed after rollback candidate was recorded.")
        rollback = self.workflow.git.rollback_to_commit(
            pre_commit, post_commit, approved=True
        )
        self.task_service.transition(
            task_id, "rolled_back", rollback=rollback
        )
        state = self._restore_state(task_id)
        if state is None:
            state = ExecutionState(task_id, max_attempts=task.max_retries)
            self._states[task_id] = state
        state.transition("rolled_back", rollback=rollback)
        state.result = {
            "ok": True,
            "stage": "rolled_back",
            "rollback": rollback,
            "rollback_candidate": candidate,
        }
        self._persist_state(task_id, state)
        return {
            "ok": True,
            "stage": "rolled_back",
            "task_id": task_id,
            "rollback": rollback,
            "state": state.snapshot(),
        }

    def get_state(self, task_id):
        state = self._restore_state(task_id)
        if state is None:
            raise PlanExecutionError(f"Unknown task: {task_id}")
        return state.snapshot()

    def _persist_state(self, task_id, state):
        task = self.task_service.get_task(task_id)
        task.result = dict(task.result)
        task.result["execution_state"] = state.snapshot()
        self.task_service.store.save(task)

    def _restore_state(self, task_id):
        state = self._states.get(task_id)
        if state is not None:
            return state
        try:
            task = self.task_service.get_task(task_id)
        except TaskServiceError:
            return None
        snapshot = task.result.get("execution_state") if isinstance(task.result, dict) else None
        if not isinstance(snapshot, dict):
            return None
        state = ExecutionState(
            task_id,
            stage=snapshot.get("stage", "created"),
            attempts=int(snapshot.get("attempts", 0)),
            max_attempts=int(snapshot.get("max_attempts", task.max_retries)),
            events=list(snapshot.get("events", [])),
            result=dict(snapshot.get("result", {})),
            steps={key: dict(value) for key, value in snapshot.get("steps", {}).items()},
        )
        if state.recover_interrupted_steps():
            self._persist_state(task_id, state)
        self._states[task_id] = state
        return state

    def resume(self, task_id):
        """Explicitly resume a task after an interrupted in-flight step."""
        state = self._restore_state(task_id)
        if state is None:
            raise PlanExecutionError(f"Unknown task: {task_id}")
        task = self.task_service.get_task(task_id)
        if not any(step.get("status") == "interrupted" for step in state.steps.values()):
            raise PlanExecutionError(f"Task '{task_id}' has no interrupted steps requiring resume.")
        if task.status not in {"executing", "failed", "testing"} and getattr(task.status, "value", task.status) not in {"executing", "failed", "testing"}:
            raise PlanExecutionError(f"Task '{task_id}' cannot be resumed from status '{task.status.value}'.")
        plan = TaskPlan.from_dict(task.plan or {})
        for step in state.steps.values():
            if step.get("status") == "interrupted":
                step["status"] = "pending"
                step["error"] = None
        self._persist_state(task_id, state)

        def checkpoint():
            self._persist_state(task_id, state)

        result = self.workflow.prepare(
            plan.actions, plan.test_target, task_id=task_id,
            step_state=state.steps, checkpoint=checkpoint,
            max_step_retries=plan.max_retries,
            expected_files=plan.expected_files,
            test_commands=plan.test_commands,
        )
        state.result = dict(result)
        self._persist_state(task_id, state)
        return {"ok": result.get("ok", False), "result": result, "state": state.snapshot()}

    @staticmethod
    def _make_task_id(plan):
        import hashlib
        return hashlib.sha256(repr(plan).encode("utf-8")).hexdigest()[:16]
