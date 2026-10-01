"""Central permission and approval policy for agent tools."""
from dataclasses import dataclass
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
    def __init__(self, grants=None):
        self._grants = set(grants or ())

    def decide(self, permission, approved=False, *, task_id=None, tool=None, arguments=None, approval=None):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        if permission.value in self._grants:
            return PermissionDecision(True, False, "permission_granted")
        if approved:
            if approval is None:
                return PermissionDecision(True, False, "explicit_approval")
            if not isinstance(approval, dict):
                return PermissionDecision(False, True, "invalid_approval")
            if task_id and approval.get("task_id") != task_id:
                return PermissionDecision(False, True, "approval_task_mismatch")
            if tool and approval.get("tool") != tool:
                return PermissionDecision(False, True, "approval_tool_mismatch")
            return PermissionDecision(True, False, "bound_approval")
        return PermissionDecision(False, True, "approval_required")

    def grant(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        self._grants.add(permission.value)

    def revoke(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        self._grants.discard(permission.value)

    def has(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        return permission.value in self._grants
