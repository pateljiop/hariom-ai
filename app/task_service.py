"""Application service for persistent task lifecycle management."""
import hashlib
from typing import Optional
from uuid import uuid4

from .task import Task, TaskStatus
from .task_store import TaskStore


class TaskServiceError(Exception):
    pass


class TaskNotFoundError(TaskServiceError):
    pass


class TaskService:
    def __init__(self, store: Optional[TaskStore] = None):
        self.store = store or TaskStore()

    def create_task(self, user_request, objective=None, **kwargs):
        if not isinstance(user_request, str) or not user_request.strip():
            raise TaskServiceError("user_request must be a non-empty string.")
        objective = objective or user_request.strip()
        task_id = kwargs.pop("task_id", None) or self._make_id(user_request, objective)
        task = Task(task_id=task_id, user_request=user_request.strip(), objective=objective.strip(), **kwargs)
        self.store.create(task)
        return task

    def get_task(self, task_id):
        task = self.store.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"Unknown task: {task_id}")
        return task

    def transition(self, task_id, status, **data):
        task = self.get_task(task_id)
        event = task.transition(status, **data)
        self.store.save(task)
        self.store.append_event(task.task_id, event)
        return task

    def cancel_task(self, task_id, reason="cancelled by user"):
        task = self.get_task(task_id)
        if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ROLLED_BACK}:
            raise TaskServiceError(f"Task cannot be cancelled from status '{task.status.value}'.")
        return self.transition(task_id, TaskStatus.CANCELLED, reason=reason)

    def events(self, task_id):
        self.get_task(task_id)
        return self.store.events(task_id)

    @staticmethod
    def _make_id(user_request, objective):
        digest = hashlib.sha256(f"{user_request}\n{objective}".encode("utf-8")).hexdigest()
        return f"task-{digest[:16]}-{uuid4().hex[:8]}"
