"""Structured tool registry for the agent execution layer.

Tools are explicit, named actions with small validated argument surfaces.
Risky tools remain approval-gated rather than becoming silently autonomous.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict

from .terminal import run_command
from .workspace import Workspace
from .workspace_patcher import TextPatch, WorkspacePatcher
from .test_runner import TestRunner
from .git_manager import GitManager


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


class ToolRegistry:
    def __init__(self, workspace=None, activity=None):
        self.workspace = workspace or Workspace()
        self.activity = activity
        self.patcher = WorkspacePatcher(self.workspace)
        self.test_runner = TestRunner(self.workspace.root)
        self.git = GitManager(self.workspace.root)
        self._tools: Dict[str, ToolSpec] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(ToolSpec(
            "workspace.list",
            "List files in the workspace.",
            lambda: [str(p.relative_to(self.workspace.root)) for p in self.workspace.list_files()],
        ))
        self.register(ToolSpec(
            "workspace.read",
            "Read a UTF-8 text file from the workspace.",
            self.workspace.read_file,
        ))
        self.register(ToolSpec(
            "workspace.write",
            "Write UTF-8 text to a file in the workspace.",
            self.workspace.write_file,
        ))
        self.register(ToolSpec(
            "terminal.run",
            "Run a shell command with existing risky-command approval controls.",
            self._run_terminal,
        ))
        self.register(ToolSpec(
            "workspace.patch",
            "Replace an exact text fragment in one workspace file.",
            self._patch_workspace,
        ))
        self.register(ToolSpec(
            "tests.run",
            "Run Python unittest discovery inside the workspace.",
            self._run_tests,
        ))
        self.register(ToolSpec(
            "git.status",
            "Show workspace Git status.",
            self.git.status,
        ))
        self.register(ToolSpec(
            "git.diff",
            "Show the current Git diff.",
            self.git.diff,
        ))
        self.register(ToolSpec(
            "git.branch",
            "Create a new isolated Git branch.",
            self.git.create_branch,
        ))
        self.register(ToolSpec(
            "git.commit",
            "Commit workspace changes; explicit approval is required.",
            self.git.commit,
            requires_approval=True,
        ))

    def register(self, spec):
        if not isinstance(spec, ToolSpec) or not spec.name:
            raise ValueError("A valid ToolSpec is required.")
        self._tools[spec.name] = spec

    def describe(self):
        return [
            {"name": spec.name, "description": spec.description, "requires_approval": spec.requires_approval}
            for spec in self._tools.values()
        ]

    def execute(self, name, arguments=None, approved=False):
        spec = self._tools.get(name)
        if spec is None:
            raise UnknownToolError(f"Unknown tool: {name}")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ToolError("Tool arguments must be an object.")
        if spec.requires_approval and not approved:
            raise ToolApprovalRequired(f"Tool '{name}' requires approval.")
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
