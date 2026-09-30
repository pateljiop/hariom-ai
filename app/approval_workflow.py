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
    approved: bool = False


class ApprovalWorkflow:
    def __init__(self, executor: Optional[TaskExecutor] = None, git=None):
        self.executor = executor or TaskExecutor()
        self.git = git or self.executor.registry.git
        self._requests: Dict[str, ApprovalRequest] = {}

    def prepare(self, actions, test_target="tests"):
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
        return {"ok": True, "request_id": request_id, "commit": result}

    @staticmethod
    def _make_request_id(actions, test_target, diff):
        import hashlib
        payload = repr((actions, test_target, diff)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]
