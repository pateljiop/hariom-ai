"""Sequential task execution over the structured tool registry."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable

from .tool_registry import ToolApprovalRequired, ToolError, ToolRegistry, UnknownToolError


@dataclass(frozen=True)
class TaskAction:
    tool: str
    arguments: Dict[str, Any]
    approved: bool = False
    dependencies: tuple = ()
    step_id: str = ""
    retryable: bool = False


class TaskExecutionError(Exception):
    """Base error for malformed task plans."""


class TaskExecutor:
    def __init__(self, registry=None):
        self.registry = registry or ToolRegistry()

    def validate(self, actions: Iterable[TaskAction]):
        if actions is None:
            raise TaskExecutionError("Actions are required.")
        normalized = list(actions)
        ids = {getattr(action, "step_id", None) for action in normalized}
        ids.discard(None)
        for action in normalized:
            if not isinstance(action, TaskAction):
                raise TaskExecutionError("Each action must be a TaskAction.")
            if not isinstance(action.arguments, dict):
                raise TaskExecutionError("Action arguments must be an object.")
            if not isinstance(action.dependencies, tuple):
                raise TaskExecutionError("Action dependencies must be a tuple.")
            if action.tool not in {item["name"] for item in self.registry.describe()}:
                raise UnknownToolError(f"Unknown tool: {action.tool}")
        return self._dependency_order(normalized)

    @staticmethod
    def _dependency_order(actions):
        if not any(getattr(a, "dependencies", ()) for a in actions):
            return actions
        indexed = {getattr(a, "step_id", f"step-{i + 1}"): a for i, a in enumerate(actions)}
        if len(indexed) != len(actions):
            raise TaskExecutionError("Step IDs must be unique for dependency-aware execution.")
        ordered, visiting, visited = [], set(), set()
        def visit(step_id):
            if step_id in visiting:
                raise TaskExecutionError(f"Circular step dependency detected at '{step_id}'.")
            if step_id in visited:
                return
            if step_id not in indexed:
                raise TaskExecutionError(f"Unknown step dependency: {step_id}")
            visiting.add(step_id)
            for dep in indexed[step_id].dependencies:
                visit(dep)
            visiting.remove(step_id)
            visited.add(step_id)
            ordered.append(indexed[step_id])
        for step_id in indexed:
            visit(step_id)
        return ordered

    @staticmethod
    def _skip_dependents(remaining, state, checkpoint):
        changed = True
        while changed:
            changed = False
            for action in remaining:
                step_id = action.step_id
                if not step_id or state.get(step_id, {}).get("status") in {"succeeded", "failed", "skipped"}:
                    continue
                if any(state.get(dep, {}).get("status") in {"failed", "skipped"} for dep in action.dependencies):
                    record = state.setdefault(step_id, {
                        "step_id": step_id, "status": "pending", "attempts": 0,
                        "result": None, "error": None,
                    })
                    record.update({"status": "skipped", "error": "dependency_failed"})
                    changed = True
                    if checkpoint:
                        checkpoint()

    def execute(self, actions, step_state=None, checkpoint: Callable | None = None, resume_interrupted=False, max_step_retries=0):
        if not isinstance(max_step_retries, int) or isinstance(max_step_retries, bool) or max_step_retries < 0 or max_step_retries > 10:
            raise TaskExecutionError("max_step_retries must be an integer between 0 and 10.")
        actions = self.validate(actions)
        results = []
        state = step_state if step_state is not None else {}
        for index, action in enumerate(actions):
            step_id = action.step_id or f"step-{index + 1}"
            record = state.setdefault(step_id, {
                "step_id": step_id, "status": "pending", "attempts": 0,
                "result": None, "error": None,
            })
            if record.get("status") == "succeeded":
                if record.get("result") is not None:
                    results.append(record["result"])
                continue
            if record.get("status") == "interrupted" and not resume_interrupted:
                return {"ok": False, "stopped": True, "index": index, "step_id": step_id,
                        "error_type": "recovery_required", "error": "Step was interrupted by a restart; explicit resume is required.", "results": results}
            if any(state.get(dep, {}).get("status") in {"failed", "skipped"} for dep in action.dependencies):
                record.update({"status": "skipped", "error": "dependency_failed"})
                if checkpoint:
                    checkpoint()
                continue
            record.update({"status": "running", "attempts": int(record.get("attempts", 0)) + 1, "error": None})
            if checkpoint:
                checkpoint()
            try:
                result = self.registry.execute(action.tool, action.arguments, approved=action.approved)
            except ToolApprovalRequired as exc:
                record.update({"status": "pending", "error": str(exc)})
                if checkpoint:
                    checkpoint()
                return {"ok": False, "stopped": True, "index": index, "step_id": step_id,
                        "error_type": "approval_required", "error": str(exc), "results": results}
            except ToolError as exc:
                if action.retryable and int(record.get("attempts", 0)) <= max_step_retries:
                    record.update({"status": "pending", "error": str(exc)})
                    if checkpoint:
                        checkpoint()
                    continue
                record.update({"status": "failed", "error": str(exc)})
                self._skip_dependents(actions[index + 1:], state, checkpoint)
                if checkpoint:
                    checkpoint()
                return {"ok": False, "stopped": True, "index": index, "step_id": step_id,
                        "error_type": "tool_error", "error": str(exc), "results": results}
            if not result.get("ok"):
                if action.retryable and int(record.get("attempts", 0)) <= max_step_retries:
                    record.update({"status": "pending", "error": result.get("error"), "result": result})
                    if checkpoint:
                        checkpoint()
                    continue
                record.update({"status": "failed", "error": result.get("error"), "result": result})
                self._skip_dependents(actions[index + 1:], state, checkpoint)
                if checkpoint:
                    checkpoint()
                return {"ok": False, "stopped": True, "index": index, "step_id": step_id,
                        "error_type": "execution_error", "error": result.get("error"), "results": results}
            record.update({"status": "succeeded", "result": result, "error": None})
            results.append(result)
            if checkpoint:
                checkpoint()
        return {"ok": True, "stopped": False, "results": results}
