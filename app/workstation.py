"""Unified desktop workstation facade.

Keeps the existing task/plan/approval architecture as the single execution
boundary for UI and background requests. The UI never calls tools directly.
"""
from threading import RLock
from uuid import uuid4

from .activity import ActivityBus
from .agent_execution import AgentExecutionFacade
from .agent_runner import AgentRunner
from .plan_executor import PlanExecutor
from .task_executor import TaskExecutor
from .task_queue import TaskQueue
from .task_service import TaskService
from .task_plan import TaskPlan
from .tool_registry import ToolRegistry
from .approval_workflow import ApprovalWorkflow


class WorkstationError(Exception):
    pass


class Workstation:
    def __init__(self, activity=None, workspace=None, max_workers=2):
        self.activity = activity or ActivityBus()
        self.registry = ToolRegistry(workspace=workspace, activity=self.activity)
        self.task_service = TaskService()
        self.task_executor = TaskExecutor(self.registry)
        self.workflow = ApprovalWorkflow(executor=self.task_executor, git=self.registry.git, store=self.task_service.store)
        self.executor = PlanExecutor(workflow=self.workflow, task_service=self.task_service)
        # Reuse the exact registry/executor path; no duplicate execution stack.
        self.agent = AgentRunner(
            router=None,
            facade=AgentExecutionFacade(
                tool_registry=self.registry,
                executor=self.executor,
            ),
        )
        self.queue = TaskQueue(max_workers=max_workers)
        self._lock = RLock()
        self.recover_background_tasks()

    def attach_router(self, router):
        if router is None:
            raise WorkstationError("router is required")
        self.agent.router = router
        return self

    def plan(self, request, **kwargs):
        self._require_router()
        return self.agent.plan(request, **kwargs)

    def prepare(self, request, **kwargs):
        self._require_router()
        self.activity.emit("AGENT -> planning and validating task")
        result = self.agent.prepare(request, **kwargs)
        self.activity.emit(
            "AGENT -> " + ("approval required" if result.get("ok") else "execution failed")
        )
        return result

    def run(self, request, **kwargs):
        self._require_router()
        self.activity.emit("AGENT -> executing task")
        result = self.agent.run(request, **kwargs)
        self.activity.emit(
            "AGENT -> completed" if result.get("ok") else "AGENT -> failed"
        )
        return result

    def submit_background(self, request, **kwargs):
        """Plan synchronously, persist the task, then execute it on a bounded worker."""
        self._require_router()
        planned = self.agent.plan(request, **kwargs)
        plan = TaskPlan.from_dict(planned["plan"])
        task_id = "task-bg-" + uuid4().hex[:16]
        task = self.task_service.create_task(
            plan.user_request or request,
            objective=plan.objective or plan.user_request or request,
            task_id=task_id,
            steps=tuple(plan.steps),
            dependencies=tuple(plan.dependencies),
            expected_files=tuple(plan.expected_files),
            test_commands=tuple(plan.test_commands),
            risk_level=plan.risk_level,
            required_approvals=tuple(plan.required_approvals),
            rollback_strategy=plan.rollback_strategy,
            max_retries=plan.max_retries,
            plan=plan.to_dict(),
        )
        task.result["background"] = True
        task.result["queue_status"] = "queued"
        self.task_service.store.save(task)
        self.activity.emit("TASK -> queued " + task_id)

        def execute():
            self.activity.emit("TASK -> worker started " + task_id)
            return self.executor.prepare(plan.to_dict(), task_id=task_id)

        return self.queue.submit(task_id, execute)

    def recover_background_tasks(self):
        """Requeue persisted background tasks that are not terminal."""
        try:
            tasks = self.task_service.list_tasks()
        except Exception:
            return []
        recovered = []
        terminal = {
            "completed", "cancelled", "rolled_back",
            "awaiting_commit_approval", "committing",
        }
        for task in tasks:
            if not isinstance(task.result, dict) or not task.result.get("background"):
                continue
            status = getattr(task.status, "value", str(task.status))
            if status in terminal or not isinstance(task.plan, dict):
                continue
            try:
                result = self.queue.submit(
                    task.task_id,
                    lambda p=task.plan, tid=task.task_id: self.executor.prepare(p, task_id=tid),
                )
                recovered.append(result)
                self.activity.emit("TASK -> restart recovery " + task.task_id)
            except Exception:
                continue
        return recovered

    def status(self, task_id):
        state = self.executor.get_state(task_id)
        queued = None
        try:
            queued = self.queue.status(task_id)
        except Exception:
            pass
        return {"task": state, "queue": queued}

    def cancel(self, task_id):
        cancelled = False
        queued = False
        try:
            cancelled = self.queue.cancel(task_id).get("cancelled", False)
            queued = True
        except Exception:
            pass
        if not cancelled and queued:
            raise WorkstationError(
                f"Task '{task_id}' is already running and cannot be cancelled safely."
            )
        task = self.task_service.cancel_task(task_id)
        self.activity.emit("TASK -> cancelled " + task_id)
        return {"task_id": task_id, "cancelled": cancelled, "status": task.status.value}

    def approve(self, request_id, message):
        self._require_router()
        result = self.agent.facade.approve(request_id, message)
        self.activity.emit("APPROVAL -> committed " + request_id)
        return result

    def reject(self, request_id, reason="rejected by user"):
        result = self.agent.facade.executor.workflow.reject(request_id, reason)
        self.activity.emit("APPROVAL -> rejected " + request_id)
        return result

    def run_tool_loop(self, request, **kwargs):
        self._require_router()
        self.activity.emit("AGENT -> native tool loop started")
        result = self.agent.run_tool_loop(request, **kwargs)
        status = result.get("status") if isinstance(result, dict) else None
        self.activity.emit("AGENT -> tool loop " + (status or "finished"))
        return result

    def run_browser(self, request, **kwargs):
        self._require_router()
        self.activity.emit("BROWSER AGENT -> started")
        return self.agent.run_browser(request, **kwargs)

    def run_computer(self, request, **kwargs):
        self._require_router()
        self.activity.emit("COMPUTER AGENT -> started")
        return self.agent.run_computer(request, **kwargs)

    def shutdown(self):
        self.queue.shutdown(wait=False)

    def _require_router(self):
        if self.agent.router is None:
            raise WorkstationError("AI router is not attached.")
