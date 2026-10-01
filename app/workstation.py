"""Unified desktop workstation facade.

Keeps the existing task/plan/approval architecture as the single execution
boundary for UI and background requests. The UI never calls tools directly.
"""
from threading import RLock

from .activity import ActivityBus
from .agent_execution import AgentExecutionFacade
from .agent_runner import AgentRunner
from .plan_executor import PlanExecutor
from .task_queue import TaskQueue
from .task_service import TaskService
from .tool_registry import ToolRegistry


class WorkstationError(Exception):
    pass


class Workstation:
    def __init__(self, activity=None, workspace=None, max_workers=2):
        self.activity = activity or ActivityBus()
        self.registry = ToolRegistry(workspace=workspace, activity=self.activity)
        self.task_service = TaskService()
        self.executor = PlanExecutor(task_service=self.task_service)
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
        self._require_router()
        prepared = self.prepare(request, **kwargs)
        state = prepared.get("state", {})
        task_id = state.get("task_id") if isinstance(state, dict) else None
        if not task_id:
            raise WorkstationError("Prepared task did not return a persistent task ID.")

        def execute():
            return self.executor.get_state(task_id)

        return self.queue.submit(task_id, execute)

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
        try:
            cancelled = self.queue.cancel(task_id).get("cancelled", False)
        except Exception:
            pass
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
