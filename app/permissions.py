"""Central permission and approval policy for agent tools."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
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


class ApprovalAuthority:
    """Mints and verifies opaque, exact, expiring, one-time approval tokens."""

    def __init__(self, secret=None):
        self._secret = secret or secrets.token_bytes(32)
        self._consumed = set()

    @staticmethod
    def _payload(task_id, tool, permission, arguments, expires_at, nonce):
        return json.dumps({
            "task_id": task_id or "",
            "tool": tool or "",
            "permission": permission,
            "arguments_hash": PermissionManager.argument_fingerprint(arguments),
            "expires_at": expires_at,
            "nonce": nonce,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def issue(self, *, task_id, tool, permission, arguments, ttl_seconds=1800):
        if not task_id or not tool:
            raise ValueError("task_id and tool are required for bound approval.")
        expires_at = (datetime.now(timezone.utc).timestamp() + ttl_seconds)
        expires_text = datetime.fromtimestamp(expires_at, timezone.utc).isoformat()
        nonce = secrets.token_urlsafe(18)
        payload = self._payload(task_id, tool, str(permission), arguments, expires_text, nonce)
        signature = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return f"v1.{nonce}.{signature}"

    def verify(self, token, *, task_id, tool, permission, arguments):
        if not isinstance(token, str):
            return PermissionDecision(False, True, "invalid_approval_token")
        parts = token.split(".", 2)
        if len(parts) != 3 or parts[0] != "v1":
            return PermissionDecision(False, True, "invalid_approval_token")
        nonce, signature = parts[1], parts[2]
        # Token metadata is intentionally not trusted from the caller. We retain
        # the bound request data in the signed token, but need the expiry to verify
        # it; decode it from the signed token payload stored in the nonce registry.
        record = getattr(self, "_issued", {}).get(nonce)
        if record is None:
            return PermissionDecision(False, True, "unknown_approval_token")
        payload = self._payload(
            record["task_id"], record["tool"], record["permission"],
            record["arguments"], record["expires_at"], nonce
        )
        expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return PermissionDecision(False, True, "invalid_approval_token")
        if nonce in self._consumed:
            return PermissionDecision(False, True, "approval_consumed")
        if datetime.now(timezone.utc) >= datetime.fromisoformat(record["expires_at"]):
            return PermissionDecision(False, True, "approval_expired")
        if record["task_id"] != task_id or record["tool"] != tool:
            return PermissionDecision(False, True, "approval_binding_mismatch")
        if record["permission"] != str(permission):
            return PermissionDecision(False, True, "approval_permission_mismatch")
        if record["arguments_hash"] != PermissionManager.argument_fingerprint(arguments):
            return PermissionDecision(False, True, "approval_arguments_mismatch")
        self._consumed.add(nonce)
        return PermissionDecision(True, False, "bound_approval_token")

    def issue(self, *, task_id, tool, permission, arguments, ttl_seconds=1800):
        if not task_id or not tool:
            raise ValueError("task_id and tool are required for bound approval.")
        expires_at = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + ttl_seconds, timezone.utc
        ).isoformat()
        nonce = secrets.token_urlsafe(18)
        record = {
            "task_id": task_id, "tool": tool, "permission": str(permission),
            "arguments": arguments or {}, "arguments_hash": PermissionManager.argument_fingerprint(arguments),
            "expires_at": expires_at,
        }
        if not hasattr(self, "_issued"):
            self._issued = {}
        self._issued[nonce] = record
        payload = self._payload(task_id, tool, str(permission), arguments, expires_at, nonce)
        signature = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return f"v1.{nonce}.{signature}"


class PermissionManager:
    """Central gate for capabilities and exact, expiring task approvals."""

    def __init__(self, grants=None, approval_authority=None):
        self._grants = set(grants or ())
        self.approval_authority = approval_authority or ApprovalAuthority()

    @staticmethod
    def argument_fingerprint(arguments=None):
        payload = json.dumps(arguments or {}, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def decide(self, permission, approved=False, *, task_id=None, tool=None, arguments=None, approval=None, approval_token=None):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        if task_id is None and permission.value in self._grants:
            return PermissionDecision(True, False, "permission_granted")
        if approval_token is not None:
            return self.approval_authority.verify(
                approval_token, task_id=task_id, tool=tool,
                permission=permission.value, arguments=arguments
            )
        if not approved:
            return PermissionDecision(False, True, "approval_required")
        if approval is None:
            if task_id:
                return PermissionDecision(False, True, "bound_approval_required")
            return PermissionDecision(True, False, "explicit_approval")
        # Legacy approval dictionaries are no longer authorization credentials.
        return PermissionDecision(False, True, "untrusted_approval_record")

    def issue_approval_token(self, *, task_id, tool, permission, arguments, ttl_seconds=1800):
        if not task_id or not tool:
            raise PermissionError("Only task-bound approvals can mint approval tokens.")
        return self.approval_authority.issue(
            task_id=task_id, tool=tool, permission=permission,
            arguments=arguments, ttl_seconds=ttl_seconds
        )

    def grant(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        self._grants.add(permission.value)

    def revoke(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        self._grants.discard(permission.value)

    def has(self, permission):
        permission = permission if isinstance(permission, Permission) else Permission(permission)
        return permission.value in self._grants
