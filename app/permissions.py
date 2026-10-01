"""Central permission and approval policy for agent tools."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from enum import Enum


class Permission(str, Enum):
    WORKSPACE_READ = "workspace.read"
    WORKSPACE_WRITE = "workspace.write"
    WORKSPACE_DELETE = "workspace.delete"
    TERMINAL_EXECUTE = "terminal.execute"
    GIT_COMMIT = "git.commit"
    BROWSER_READ = "browser.read"
    BROWSER_CLICK = "browser.click"
    BROWSER_TYPE = "browser.type"
    COMPUTER_SCREENSHOT = "computer.screenshot"
    COMPUTER_KEYBOARD = "computer.keyboard"
    EXTERNAL_NETWORK = "external_network"
    SECRETS_ACCESS = "secrets_access"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    reason: str = ""


class PermissionManager:
    """Central gate for capabilities and exact, expiring task approvals."""

    def __init__(self, grants=None):
        self._grants = set(grants or ())

    @staticmethod
    def argument_fingerprint(arguments=None):
        payload = json.dumps(arguments or {}, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def decide(self, permission, approved=False, *, task_id=None, tool=None, arguments=None, approval=None):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        if task_id is None and permission.value in self._grants:
            return PermissionDecision(True, False, "permission_granted")
        if not approved:
            return PermissionDecision(False, True, "approval_required")
        if approval is None:
            if task_id:
                return PermissionDecision(False, True, "bound_approval_required")
            return PermissionDecision(True, False, "explicit_approval")
        if not isinstance(approval, dict):
            return PermissionDecision(False, True, "invalid_approval")
        if task_id and approval.get("task_id") != task_id:
            return PermissionDecision(False, True, "approval_task_mismatch")
        if tool and approval.get("tool") != tool:
            return PermissionDecision(False, True, "approval_tool_mismatch")
        approved_permissions = set(approval.get("permissions", ()))
        if approval.get("permission") not in {None, permission.value} and permission.value not in approved_permissions:
            return PermissionDecision(False, True, "approval_permission_mismatch")
        if "arguments_hash" in approval and approval["arguments_hash"] != self.argument_fingerprint(arguments):
            return PermissionDecision(False, True, "approval_arguments_mismatch")
        expires_at = approval.get("expires_at")
        if expires_at:
            try:
                if datetime.now(timezone.utc) >= datetime.fromisoformat(expires_at):
                    return PermissionDecision(False, True, "approval_expired")
            except (TypeError, ValueError):
                return PermissionDecision(False, True, "invalid_approval_expiry")
        if approval.get("consumed"):
            return PermissionDecision(False, True, "approval_consumed")
        return PermissionDecision(True, False, "bound_approval")

    def grant(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        self._grants.add(permission.value)

    def revoke(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        self._grants.discard(permission.value)

    def has(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        return permission.value in self._grants
