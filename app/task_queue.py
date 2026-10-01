"""Bounded background task execution queue."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class TaskQueueError(Exception):
    pass


class TaskQueue:
    def __init__(self, max_workers=2):
        if not isinstance(max_workers, int) or isinstance(max_workers, bool) or not 1 <= max_workers <= 8:
            raise TaskQueueError("max_workers must be between 1 and 8.")
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="hariom-task")
        self._lock = Lock()
        self._jobs = {}

    def submit(self, task_id, fn, *args, **kwargs):
        if not isinstance(task_id, str) or not task_id.strip():
            raise TaskQueueError("task_id is required.")
        if not callable(fn):
            raise TaskQueueError("fn must be callable.")
        with self._lock:
            existing = self._jobs.get(task_id)
            if existing and not existing.done():
                raise TaskQueueError(f"Task '{task_id}' is already running.")
            future = self.executor.submit(fn, *args, **kwargs)
            self._jobs[task_id] = future
        return {"task_id": task_id, "status": "queued"}

    def status(self, task_id):
        with self._lock:
            future = self._jobs.get(task_id)
        if future is None:
            raise TaskQueueError(f"Unknown queued task: {task_id}")
        if future.cancelled():
            return {"task_id": task_id, "status": "cancelled"}
        if not future.done():
            return {"task_id": task_id, "status": "running"}
        try:
            return {"task_id": task_id, "status": "completed", "result": future.result()}
        except Exception as exc:
            return {"task_id": task_id, "status": "failed", "error": str(exc)}

    def cancel(self, task_id):
        with self._lock:
            future = self._jobs.get(task_id)
        if future is None:
            raise TaskQueueError(f"Unknown queued task: {task_id}")
        return {"task_id": task_id, "cancelled": future.cancel()}

    def shutdown(self, wait=True):
        self.executor.shutdown(wait=wait, cancel_futures=True)
