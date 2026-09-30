"""Sequential task execution over the structured tool registry."""
from dataclasses import dataclass
from typing import Any, Dict, Iterable

from .tool_registry import ToolApprovalRequired, ToolError, ToolRegistry, UnknownToolError


@dataclass(frozen=True)
class TaskAction:
    tool: str
    arguments: Dict[str, Any]
    approved: bool = False


class TaskExecutionError(Exception):
    """Base error for malformed task plans."""


class TaskExecutor:
    def __init__(self, registry=None):
        self.registry = registry or ToolRegistry()

    def validate(self, actions: Iterable[TaskAction]):
        if actions is None:
            raise TaskExecutionError("Actions are required.")
        normalized = list(actions)
        for action in normalized:
            if not isinstance(action, TaskAction):
                raise TaskExecutionError("Each action must be a TaskAction.")
            if not isinstance(action.arguments, dict):
                raise TaskExecutionError("Action arguments must be an object.")
            if action.tool not in {item["name"] for item in self.registry.describe()}:
                raise UnknownToolError(f"Unknown tool: {action.tool}")
        return normalized

    def execute(self, actions):
        actions = self.validate(actions)
        results = []
        for index, action in enumerate(actions):
            try:
                result = self.registry.execute(action.tool, action.arguments, approved=action.approved)
            except ToolApprovalRequired as exc:
                return {"ok": False, "stopped": True, "index": index, "error_type": "approval_required", "error": str(exc), "results": results}
            except ToolError as exc:
                return {"ok": False, "stopped": True, "index": index, "error_type": "tool_error", "error": str(exc), "results": results}
            if not result.get("ok"):
                return {"ok": False, "stopped": True, "index": index, "error_type": "execution_error", "error": result.get("error"), "results": results}
            results.append(result)
        return {"ok": True, "stopped": False, "results": results}
