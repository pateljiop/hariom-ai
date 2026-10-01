"""Approval-gated workflow with persistent, expiring approval requests."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional
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
    commit_result: object = None
    branch_name: str = ""


class ApprovalWorkflow:
    def __init__(self, executor: Optional[TaskExecutor] = None, git=None, store=None, approval_ttl_seconds=1800):
        self.executor = executor or TaskExecutor()
        self.git = git or self.executor.registry.git
        self.store = store
        self.approval_ttl_seconds = approval_ttl_seconds
        self._requests: Dict[str, ApprovalRequest] = {}

    def prepare(self, actions, test_target="tests", task_id="", step_state=None, checkpoint: Callable | None = None, max_step_retries=0, expected_files=(), test_commands=()):
        if actions is None:
            raise ApprovalWorkflowError("Actions are required.")
        actions = tuple(actions)
        try:
            execution = self.executor.execute(
                actions, step_state=step_state, checkpoint=checkpoint,
                max_step_retries=max_step_retries, task_id=task_id or None
            )
        except TaskExecutionError:
            raise
        if not execution["ok"]:
            return {"ok": False, "stage": "execution", "execution": execution}
        expectation_result = self.executor.verify_expectations(expected_files, test_commands)
        if not expectation_result["ok"]:
            return {"ok": False, "stage": "verification", "execution": execution, "expectation_result": expectation_result}
        test_result = self.executor.registry.test_runner.run(test_target)
        if not test_result["ok"]:
            return {"ok": False, "stage": "verification", "execution": execution, "expectation_result": expectation_result, "test_result": test_result}
        diff = self.git.diff()
        branch_name = self.git.current_branch()
        request_id = 'approval-' + uuid4().hex
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.approval_ttl_seconds)
        request = ApprovalRequest(
            request_id=request_id, actions=actions, test_target=test_target,
            test_result=test_result, diff=diff, task_id=task_id,
            created_at=now.isoformat(), expires_at=expires.isoformat(), branch_name=branch_name,
        )
        self._requests[request_id] = request
        self._persist(request, "pending")
        return {
            "ok": True, "stage": "approval", "request_id": request_id,
            "execution": execution, "expectation_result": expectation_result,
            "test_result": test_result, "diff": diff,
            "expires_at": request.expires_at,
        }

    def approve(self, request_id, message):
        request = self._load(request_id)
        if request.approved:
            return {"ok": True, "request_id": request_id, "commit": getattr(request, "commit_result", None), "idempotent": True}
        self._ensure_pending(request)
        if not isinstance(message, str) or not message.strip():
            raise ApprovalWorkflowError("Commit message is required.")
        if datetime.now(timezone.utc) >= datetime.fromisoformat(request.expires_at):
            raise ApprovalDeniedError("Approval request has expired.")
        if self.git.current_branch() != request.branch_name:
            raise ApprovalWorkflowError("Git branch changed after review; approval is invalid.")
        if self.git.diff() != request.diff:
            raise ApprovalWorkflowError("Workspace diff changed after review; approval is invalid.")
        pre_commit_head = self.git.head_sha()
        result = self.git.commit(message, approved=True)
        post_commit_head = self.git.head_sha()
        if post_commit_head == pre_commit_head:
            raise ApprovalWorkflowError("Git commit did not advance HEAD; commit verification failed.")
        if self.git.current_branch() != request.branch_name:
            raise ApprovalWorkflowError("Git branch changed during commit; commit verification failed.")
        commit_result = {
            "result": result,
            "pre_commit_head": pre_commit_head,
            "post_commit_head": post_commit_head,
            "branch_name": request.branch_name,
        }
        consumed = ApprovalRequest(**{**request.__dict__, "approved": True, "commit_result": commit_result})
        self._requests[request_id] = consumed
        self._persist(consumed, "approved")
        tokens = self.issue_action_tokens(request_id)
        return {"ok": True, "request_id": request_id, "commit": commit_result, "approval_tokens": tokens}

    def issue_action_tokens(self, request_id):
        request = self._load(request_id)
        if not request.approved:
            raise ApprovalDeniedError("Approval request must be approved before action tokens are issued.")
        if datetime.now(timezone.utc) >= datetime.fromisoformat(request.expires_at):
            raise ApprovalDeniedError("Approval request has expired.")
        if not request.task_id:
            return {}
        tokens = {}
        for action in request.actions:
            spec = next((item for item in self.executor.registry.describe() if item["name"] == action.tool), None)
            if spec is None or not spec.get("permission"):
                continue
            permissions = [spec["permission"]]
            permissions.extend(self.executor.registry.additional_permissions(action.tool, action.arguments))
            tokens[action.step_id or action.tool] = self.executor.registry.permission_manager.issue_approval_token(
                task_id=request.task_id,
                tool=action.tool,
                permission=permissions,
                arguments=action.arguments,
                ttl_seconds=max(1, int(
                    (datetime.fromisoformat(request.expires_at) - datetime.now(timezone.utc)).total_seconds()
                )),
            )
        return tokens

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
                    actions=tuple(TaskAction(
                        tool=x["tool"], arguments=x.get("arguments", {}), approved=x.get("approved", False),
                        approval_token=x.get("approval_token", ""),
                        dependencies=tuple(x.get("dependencies", [])), step_id=x.get("step_id", ""),
                        retryable=x.get("retryable", False),
                        expected_files=tuple(x.get("expected_files", [])),
                        test_commands=tuple(x.get("test_commands", []))
                    ) for x in saved["actions"]),
                    test_target=saved["test_target"], test_result=saved["test_result"],
                    diff=saved["diff"], task_id=saved.get("task_id", ""),
                    created_at=saved["created_at"], expires_at=saved["expires_at"],
                    approved=saved["status"] == "approved",
                    rejected=saved["status"] == "rejected",
                    commit_result=saved.get("commit_result"), branch_name=saved.get("branch_name", ""),
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
            "actions": [{
                "tool": a.tool, "arguments": dict(a.arguments), "approved": a.approved,
                "approval_token": a.approval_token,
                "dependencies": list(a.dependencies), "step_id": a.step_id, "retryable": a.retryable,
                "expected_files": list(a.expected_files), "test_commands": list(a.test_commands),
            } for a in request.actions],
            "test_target": request.test_target,
            "test_result": request.test_result,
            "diff": request.diff,
            "commit_result": request.commit_result,
            "branch_name": request.branch_name,
        }
        self.store.save_approval(request.request_id, payload, request.created_at, request.expires_at, status)

    @staticmethod
    def _make_request_id(actions, test_target, diff):
        import hashlib
        payload = repr((actions, test_target, diff)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]
