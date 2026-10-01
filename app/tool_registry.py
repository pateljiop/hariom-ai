"""Structured tool registry with schema and central permission enforcement."""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .terminal import run_command
from .workspace import Workspace
from .workspace_patcher import TextPatch, WorkspacePatcher
from .test_runner import TestRunner
from .git_manager import GitManager
from .browser import BrowserController
from .computer import ComputerController
from .tool_schema import ToolSchema, ToolSchemaError
from .permissions import Permission, PermissionManager


class ToolError(Exception):
    """Base error for tool execution failures."""


class UnknownToolError(ToolError):
    pass


class ToolApprovalRequired(ToolError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    requires_approval: bool = False
    schema: ToolSchema = ToolSchema()
    version: str = "1.0"
    return_schema: Optional[Dict[str, Any]] = None
    risk: str = "low"
    permission: Optional[str] = None
    timeout: int = 120
    retry: int = 0
    rollback: str = "none"
    limits: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self, workspace=None, activity=None, permission_manager=None):
        self.workspace = workspace or Workspace()
        self.activity = activity
        self.permission_manager = permission_manager or PermissionManager(
            grants=(
                Permission.WORKSPACE_READ,
                Permission.WORKSPACE_WRITE,
                Permission.TERMINAL_EXECUTE,
            )
        )
        self.patcher = WorkspacePatcher(self.workspace)
        self.test_runner = TestRunner(self.workspace.root)
        self.git = GitManager(self.workspace.root)
        self.browser = BrowserController(self.activity)
        self.computer = ComputerController(self.activity)
        self._tools: Dict[str, ToolSpec] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(ToolSpec("workspace.list", "List files in the workspace.", lambda: [str(p.relative_to(self.workspace.root)) for p in self.workspace.list_files()], permission=Permission.WORKSPACE_READ.value, return_schema={"type": "array", "items": {"type": "string"}}))
        self.register(ToolSpec("workspace.read", "Read a UTF-8 text file from the workspace.", self.workspace.read_file, schema=ToolSchema(required=("path",), types={"path": (str,)}), permission=Permission.WORKSPACE_READ.value, return_schema={"type": "object"}))
        self.register(ToolSpec("workspace.write", "Write UTF-8 text to a file in the workspace.", self.workspace.write_file, schema=ToolSchema(required=("path", "content"), types={"path": (str,), "content": (str,)}), permission=Permission.WORKSPACE_WRITE.value, return_schema={"type": "object"}))
        self.register(ToolSpec("terminal.run", "Run a shell command with existing risky-command approval controls.", self._run_terminal, schema=ToolSchema(required=("command",), optional=("approved",), types={"command": (str,), "approved": (bool,)}), permission=Permission.TERMINAL_EXECUTE.value, risk="high", requires_approval=True, return_schema={"type": "object"}))
        self.register(ToolSpec("workspace.patch", "Replace an exact text fragment in one workspace file.", self._patch_workspace, schema=ToolSchema(required=("path", "old", "new"), optional=("expected_count",), types={"path": (str,), "old": (str,), "new": (str,), "expected_count": (int,)}), permission=Permission.WORKSPACE_WRITE.value, return_schema={"type": "object"}))
        self.register(ToolSpec("tests.run", "Run Python unittest discovery inside the workspace.", self._run_tests, schema=ToolSchema(optional=("target",), types={"target": (str,)}), permission=Permission.TERMINAL_EXECUTE.value, risk="medium", return_schema={"type": "object"}))
        self.register(ToolSpec("browser.open", "Open a URL in the browser.", self.browser.open, schema=ToolSchema(required=("url",), types={"url": (str,)}), permission=Permission.EXTERNAL_NETWORK.value, requires_approval=True, risk="high", return_schema={"type": "object"}))
        self.register(ToolSpec("browser.read", "Read the current browser page.", self.browser.read_text, schema=ToolSchema(optional=("selector",), types={"selector": (str,)}), permission=Permission.BROWSER_READ.value, risk="low", return_schema={"type": "string"}))
        self.register(ToolSpec("browser.observe", "Observe the current browser URL, title, and visible text.", self.browser.observe, schema=ToolSchema(optional=("selector",), types={"selector": (str,)}), permission=Permission.BROWSER_READ.value, risk="low", return_schema={"type": "object"}))
        self.register(ToolSpec("browser.verify", "Verify explicit browser state conditions.", self.browser.verify, schema=ToolSchema(optional=("selector", "text", "url_contains"), types={"selector": (str,), "text": (str,), "url_contains": (str,)}), permission=Permission.BROWSER_READ.value, risk="low", return_schema={"type": "object"}))
        self.register(ToolSpec("browser.find", "Find browser elements by CSS selector, optionally filtering by visible text.", self.browser.find, schema=ToolSchema(required=("selector",), optional=("text",), types={"selector": (str,), "text": (str,)}), permission=Permission.BROWSER_READ.value, risk="low", return_schema={"type": "object"}))
        self.register(ToolSpec("browser.click", "Click a browser element.", self.browser.click, schema=ToolSchema(required=("selector",), optional=("approved",), types={"selector": (str,), "approved": (bool,)}), permission=Permission.BROWSER_CLICK.value, requires_approval=True, risk="high", return_schema={"type": "object"}))
        self.register(ToolSpec("browser.type", "Type into a browser field.", self.browser.type_text, schema=ToolSchema(required=("selector", "text"), optional=("approved", "sensitive"), types={"selector": (str,), "text": (str,), "approved": (bool,), "sensitive": (bool,)}), permission=Permission.BROWSER_TYPE.value, requires_approval=True, risk="high", return_schema={"type": "object"}))
        self.register(ToolSpec("browser.screenshot", "Capture the current browser view temporarily; persistence must be explicitly requested.", self.browser.screenshot, schema=ToolSchema(optional=("path", "approved", "persist"), types={"path": (str,), "approved": (bool,), "persist": (bool,)}), permission=Permission.COMPUTER_SCREENSHOT.value, requires_approval=True, risk="high", return_schema={"type": "object"}))
        self.register(ToolSpec("computer.screen_size", "Read the current screen dimensions.", self.computer.screen_size, risk="low", return_schema={"type": "object"}))
        self.register(ToolSpec("computer.position", "Read the current mouse position.", self.computer.position, risk="low", return_schema={"type": "object"}))
        self.register(ToolSpec("computer.screenshot", "Capture the current computer screen temporarily; persistence must be explicitly requested.", self.computer.screenshot, schema=ToolSchema(optional=("path", "approved", "persist"), types={"path": (str,), "approved": (bool,), "persist": (bool,)}), permission=Permission.COMPUTER_SCREENSHOT.value, requires_approval=True, risk="high", return_schema={"type": "object"}))
        self.register(ToolSpec("computer.click", "Click at screen coordinates.", self.computer.click, schema=ToolSchema(optional=("x", "y", "button", "clicks", "approved"), types={"x": (int,), "y": (int,), "button": (str,), "clicks": (int,), "approved": (bool,)}, enums={"button": ("left", "middle", "right")}, min_values={"clicks": 1}, max_values={"clicks": 10}), permission=Permission.COMPUTER_KEYBOARD.value, requires_approval=True, risk="high", return_schema={"type": "boolean"}))
        self.register(ToolSpec("computer.type", "Type text on the computer.", self.computer.type_text, schema=ToolSchema(required=("text",), optional=("interval", "approved", "sensitive"), types={"text": (str,), "interval": (int, float), "approved": (bool,), "sensitive": (bool,)}), permission=Permission.COMPUTER_KEYBOARD.value, requires_approval=True, risk="high", return_schema={"type": "object"}))
        self.register(ToolSpec("computer.key", "Press an allowed keyboard key.", self.computer.press_key, schema=ToolSchema(required=("key",), optional=("approved",), types={"key": (str,), "approved": (bool,)}), permission=Permission.COMPUTER_KEYBOARD.value, requires_approval=True, risk="high", return_schema={"type": "object"}))
        self.register(ToolSpec("computer.hotkey", "Press a bounded keyboard shortcut.", self.computer.hotkey, schema=ToolSchema(required=("keys",), optional=("approved",), types={"keys": (list, tuple), "approved": (bool,)}), permission=Permission.COMPUTER_KEYBOARD.value, requires_approval=True, risk="high", return_schema={"type": "boolean"}))
        self.register(ToolSpec("git.status", "Show workspace Git status.", self.git.status, permission=Permission.WORKSPACE_READ.value, return_schema={"type": "object"}))
        self.register(ToolSpec("git.diff", "Show the current Git diff.", self.git.diff, permission=Permission.WORKSPACE_READ.value, return_schema={"type": "object"}))
        self.register(ToolSpec("git.branch", "Create a new isolated Git branch.", self.git.create_branch, schema=ToolSchema(required=("name",), types={"name": (str,)}), permission=Permission.WORKSPACE_WRITE.value, return_schema={"type": "object"}))
        self.register(ToolSpec("git.commit", "Commit workspace changes; explicit approval is required.", self.git.commit, requires_approval=True, schema=ToolSchema(required=("message",), optional=("approved",), types={"message": (str,), "approved": (bool,)}), permission=Permission.GIT_COMMIT.value, risk="high", return_schema={"type": "object"}))
        self.register(ToolSpec("git.merge", "Merge an isolated branch; explicit approval is required.", self.git.merge_branch, requires_approval=True, schema=ToolSchema(required=("name",), optional=("approved",), types={"name": (str,), "approved": (bool,)}), permission=Permission.GIT_COMMIT.value, risk="critical", return_schema={"type": "object"}))

    def register(self, spec):
        if not isinstance(spec, ToolSpec) or not spec.name:
            raise ValueError("A valid ToolSpec is required.")
        if not isinstance(spec.schema, ToolSchema):
            raise ValueError("ToolSpec.schema must be a ToolSchema.")
        if spec.return_schema is not None and not isinstance(spec.return_schema, dict):
            raise ValueError("ToolSpec.return_schema must be an object.")
        if spec.permission is not None and not isinstance(spec.permission, str):
            raise ValueError("ToolSpec.permission must be a string or None.")
        if not isinstance(spec.limits, dict):
            raise ValueError("ToolSpec.limits must be an object.")
        if not isinstance(spec.version, str) or not spec.version.strip():
            raise ValueError("ToolSpec.version must be a non-empty string.")
        if not isinstance(spec.timeout, int) or isinstance(spec.timeout, bool) or spec.timeout <= 0:
            raise ValueError("ToolSpec.timeout must be a positive integer.")
        if not isinstance(spec.retry, int) or isinstance(spec.retry, bool) or spec.retry < 0:
            raise ValueError("ToolSpec.retry must be a non-negative integer.")
        if not isinstance(spec.rollback, str) or not spec.rollback.strip():
            raise ValueError("ToolSpec.rollback must be a non-empty string.")
        if not isinstance(spec.requires_approval, bool):
            raise ValueError("ToolSpec.requires_approval must be boolean.")
        if spec.risk not in {"low", "medium", "high", "critical"}:
            raise ValueError("Tool risk must be low, medium, high, or critical.")
        self._tools[spec.name] = spec

    def describe(self):
        return [
            {
                "name": s.name, "description": s.description, "version": s.version,
                "requires_approval": s.requires_approval, "risk": s.risk,
                "permission": s.permission, "timeout": s.timeout, "retry": s.retry,
                "rollback": s.rollback, "limits": dict(s.limits),
                "input_schema": s.schema.to_dict(),
                "return_schema": s.return_schema or {
                    "type": "object",
                    "required": ["ok", "tool"],
                    "properties": {
                        "ok": {"type": "boolean"},
                        "tool": {"type": "string"},
                    },
                },
                "schema": s.schema.to_dict(),
            }
            for s in self._tools.values()
        ]

    def validate_arguments(self, name, arguments=None):
        spec = self._tools.get(name)
        if spec is None:
            raise UnknownToolError(f"Unknown tool: {name}")
        if arguments is None:
            arguments = {}
        try:
            spec.schema.validate(arguments)
        except ToolSchemaError as exc:
            raise ToolError(str(exc)) from exc
        return True

    def execute(self, name, arguments=None, approved=False, *, task_id=None, approval=None, approval_token=None):
        self.validate_arguments(name, arguments)
        spec = self._tools[name]
        if spec.permission:
            decision = self.permission_manager.decide(
                spec.permission, approved=approved, task_id=task_id, tool=name,
                arguments=arguments, approval=approval, approval_token=approval_token,
                consume_token=False
            )
            if not decision.allowed:
                raise ToolApprovalRequired(f"Tool '{name}' requires approval for permission '{spec.permission}'.")
        if arguments and arguments.get("sensitive") is True:
            decision = self.permission_manager.decide(
                Permission.SECRETS_ACCESS, approved=False, task_id=task_id, tool=name,
                arguments=arguments, approval_token=approval_token,
                consume_token=False
            )
            if not decision.allowed:
                raise ToolApprovalRequired("Sensitive input requires secrets_access approval.")
        if spec.requires_approval and not approved and approval_token is None and name != "terminal.run":
            raise ToolApprovalRequired(f"Tool '{name}' requires explicit approval.")
        if approval_token is not None and not self.permission_manager.approval_authority.consume(approval_token):
            raise ToolApprovalRequired("Approval token could not be consumed.")
        if arguments is None:
            arguments = {}
        try:
            return {"ok": True, "tool": name, "result": spec.handler(**arguments)}
        except ToolError:
            raise
        except Exception as exc:
            return {"ok": False, "tool": name, "error": str(exc)}

    def _patch_workspace(self, path, old, new, expected_count=1):
        return self.patcher.apply(TextPatch(path, old, new, expected_count))

    def _run_tests(self, target="tests"):
        return self.test_runner.run(target)

    def _run_terminal(self, command, approved=False):
        if not self.activity:
            raise ToolError("Activity bus is required for terminal execution.")
        return run_command(command, self.activity, approved=approved)
