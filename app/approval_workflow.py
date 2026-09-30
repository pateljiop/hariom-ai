"""Approval-gated workflow with persistent, expiring approval requests."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import uuid4

from .task_executor import TaskAction, TaskExecutor, TaskExecutionError


class ApprovalWorkflowError(Exception):
    pass


class ApprovalNotFoundError(ApprovalWorkflowError):
    pass


class ApprovalDeniedError(ApprovalWorkflowError):
    pass


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    actions: tuple
    test_target: str
    test_result: dict
    diff: str
    approved: bool = False
    task_id: str = ""
    created_at: str = ""
    expires_at: str = ""
    rejected: bool = False


class ApprovalWorkflow:
    def __init__(self, executor: Optional[TaskExecutor] = None, git=None, store=None, approval_ttl_seconds=1800):
        self.executor = executor or TaskExecutor()
        self.git = git or self.executor.registry.git
        self.store = store
        self.approval_ttl_seconds = approval_ttl_seconds
        self._requests: Dict[str, ApprovalRequest] = {}

    def prepare(self, actions, test_target="tests", task_id=""):
        if actions is None:
            raise ApprovalWorkflowError("Actions are required.")
        actions = tuple(actions)
        try:
            execution = self.executor.execute(actions)
        except TaskExecutionError:
            raise
        if not execution["ok"]:
            return {"ok": False, "stage": "execution", "execution": execution}
        test_result = self.executor.registry.test_runner.run(test_target)
        if not test_result["ok"]:
            return {"ok": False, "stage": "verification", "execution": execution, "test_result": test_result}

        diff = self.git.diff()
        request_id = 'approval-' + uuid4().hex
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.approval_ttl_seconds)
        request = ApprovalRequest(
            request_id=request_id, actions=actions, test_target=test_target,
            test_result=test_result, diff=diff, task_id=task_id,
            created_at=now.isoformat(), expires_at=expires.isoformat(),
        )
        self._requests[request_id] = request
        self._persist(request, "pending")
        return {
            "ok": True, "stage": "approval", "request_id": request_id,
            "execution": execution, "test_result": test_result, "diff": diff,
            "expires_at": request.expires_at,
        }

    def approve(self, request_id, message):
        request = self._load(request_id)
        self._ensure_pending(request)
        if not isinstance(message, str) or not message.strip():
            raise ApprovalWorkflowError("Commit message is required.")
        if datetime.now(timezone.utc) >= datetime.fromisoformat(request.expires_at):
            raise ApprovalDeniedError("Approval request has expired.")
        if self.git.diff() != request.diff:
            raise ApprovalWorkflowError("Workspace diff changed after review; approval is invalid.")

        result = self.git.commit(message, approved=True)
        consumed = ApprovalRequest(**{**request.__dict__, "approved": True})
        self._requests[request_id] = consumed
        self._persist(consumed, "approved")
        return {"ok": True, "request_id": request_id, "commit": result}

    def reject(self, request_id, reason="rejected by user"):
        request = self._load(request_id)
        self._ensure_pending(request)
        rejected = ApprovalRequest(**{**request.__dict__, "rejected": True})
        self._requests[request_id] = rejected
        self._persist(rejected, "rejected")
        return {"ok": True, "request_id": request_id, "rejected": True, "reason": reason}

    def _load(self, request_id):
        request = self._requests.get(request_id)
        if request is not None:
            return request
        if self.store:
            saved = self.store.get_approval(request_id)
            if saved:
                request = ApprovalRequest(
                    request_id=request_id,
                    actions=tuple(TaskAction(x["tool"], x.get("arguments", {}), x.get("approved", False)) for x in saved["actions"]),
                    test_target=saved["test_target"], test_result=saved["test_result"],
                    diff=saved["diff"], task_id=saved.get("task_id", ""),
                    created_at=saved["created_at"], expires_at=saved["expires_at"],
                    approved=saved["status"] == "approved",
                    rejected=saved["status"] == "rejected",
                )
                self._requests[request_id] = request
                return request
        raise ApprovalNotFoundError(f"Unknown approval request: {request_id}")

    @staticmethod
    def _ensure_pending(request):
        if request.approved or request.rejected:
            raise ApprovalDeniedError("Approval request has already been consumed.")

    def _persist(self, request, status):
        if not self.store:
            return
        payload = {
            "task_id": request.task_id,
            "actions": [{"tool": a.tool, "arguments": dict(a.arguments), "approved": a.approved} for a in request.actions],
            "test_target": request.test_target,
            "test_result": request.test_result,
            "diff": request.diff,
        }
        self.store.save_approval(request.request_id, payload, request.created_at, request.expires_at, status)

    @staticmethod
    def _make_request_id(actions, test_target, diff):
        import hashlib
        payload = repr((actions, test_target, diff)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]
