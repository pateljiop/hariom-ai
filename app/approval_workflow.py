"""Approval-gated workflow for controlled agent changes.

The workflow deliberately separates mutation, verification, review, and commit.
No commit can happen until verification succeeds and the specific request is approved.
"""
from dataclasses import dataclass
from typing import Dict, Optional

from .task_executor import TaskAction, TaskExecutor, TaskExecutionError


class ApprovalWorkflowError(Exception):
    """Base error for approval workflow failures."""


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
    approved: bool = False\n    task_id: str = ""\n    created_at: str = ""\n    expires_at: str = ""\n    rejected: bool = False


class ApprovalWorkflow:
    def __init__(self, executor: Optional[TaskExecutor] = None, git=None):
        self.executor = executor or TaskExecutor()
        self.git = git or self.executor.registry.git
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
            return {
                "ok": False,
                "stage": "verification",
                "execution": execution,
                "test_result": test_result,
            }

        diff = self.git.diff()
        request_id = self._make_request_id(actions, test_target, diff)
        request = ApprovalRequest(
            request_id=request_id,
            actions=actions,
            test_target=test_target,
            test_result=test_result,
            diff=diff,
        )
        self._requests[request_id] = request
        return {
            "ok": True,
            "stage": "approval",
            "request_id": request_id,
            "execution": execution,
            "test_result": test_result,
            "diff": diff,
        }

    def approve(self, request_id, message):
        request = self._requests.get(request_id)
        if request is None:
            raise ApprovalNotFoundError(f"Unknown approval request: {request_id}")
        if request.approved:
            raise ApprovalDeniedError("Approval request has already been consumed.")
        if not isinstance(message, str) or not message.strip():
            raise ApprovalWorkflowError("Commit message is required.")

        current_diff = self.git.diff()
        if current_diff != request.diff:
            raise ApprovalWorkflowError("Workspace diff changed after review; approval is invalid.")

        result = self.git.commit(message, approved=True)
        self._requests[request_id] = ApprovalRequest(
            request_id=request.request_id,
            actions=request.actions,
            test_target=request.test_target,
            test_result=request.test_result,
            diff=request.diff,
            approved=True,
        )
        if self.store:\n            self.store.save_approval(request_id, {"task_id": request.task_id, "actions": [{"tool": a.tool, "arguments": dict(a.arguments), "approved": a.approved} for a in request.actions], "test_target": request.test_target, "test_result": request.test_result, "diff": request.diff}, request.created_at, request.expires_at, "approved")\n        return {"ok": True, "request_id": request_id, "commit": result}\n\n    def reject(self, request_id, reason="rejected by user"):\n        request = self._requests.get(request_id)\n        if request is None and self.store:\n            saved = self.store.get_approval(request_id)\n            if saved:\n                request = ApprovalRequest(request_id=request_id, actions=tuple(TaskAction(x["tool"], x.get("arguments", {}), x.get("approved", False)) for x in saved["actions"]), test_target=saved["test_target"], test_result=saved["test_result"], diff=saved["diff"], task_id=saved.get("task_id", ""), created_at=saved["created_at"], expires_at=saved["expires_at"], approved=saved["status"] == "approved", rejected=saved["status"] == "rejected")\n        if request is None:\n            raise ApprovalNotFoundError(f"Unknown approval request: {request_id}")\n        if request.approved or request.rejected:\n            raise ApprovalDeniedError("Approval request has already been consumed.")\n        if self.store:\n            self.store.save_approval(request_id, {"task_id": request.task_id, "actions": [{"tool": a.tool, "arguments": dict(a.arguments), "approved": a.approved} for a in request.actions], "test_target": request.test_target, "test_result": request.test_result, "diff": request.diff}, request.created_at, request.expires_at, "rejected")\n        self._requests[request_id] = ApprovalRequest(**{**request.__dict__, "rejected": True})\n        return {"ok": True, "request_id": request_id, "rejected": True, "reason": reason}

    @staticmethod
    def _make_request_id(actions, test_target, diff):
        import hashlib
        payload = repr((actions, test_target, diff)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]
