"""Structured plan validation for agent execution.

Plans are JSON-friendly dictionaries that can be produced by an LLM and then
validated into typed task actions before execution.
"""
from dataclasses import dataclass
from typing import Any, Dict, Iterable

from .task_executor import TaskAction, TaskExecutionError


class PlanValidationError(TaskExecutionError):
    """Raised when an external task plan is malformed."""


@dataclass(frozen=True)
class TaskPlan:
    actions: tuple
    test_target: str = "tests"

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise PlanValidationError("Plan must be an object.")
        raw_actions = payload.get("actions")
        if not isinstance(raw_actions, list) or not raw_actions:
            raise PlanValidationError("Plan actions must be a non-empty list.")

        actions = []
        for index, raw in enumerate(raw_actions):
            if not isinstance(raw, dict):
                raise PlanValidationError(f"Action {index} must be an object.")
            tool = raw.get("tool")
            arguments = raw.get("arguments", {})
            approved = raw.get("approved", False)
            if not isinstance(tool, str) or not tool.strip():
                raise PlanValidationError(f"Action {index} has an invalid tool.")
            if not isinstance(arguments, dict):
                raise PlanValidationError(f"Action {index} arguments must be an object.")
            if not isinstance(approved, bool):
                raise PlanValidationError(f"Action {index} approved must be boolean.")
            actions.append(TaskAction(tool.strip(), arguments, approved))

        test_target = payload.get("test_target", "tests")
        if not isinstance(test_target, str) or not test_target.strip():
            raise PlanValidationError("test_target must be a non-empty string.")

        return cls(tuple(actions), test_target.strip())

    def to_dict(self):
        return {
            "actions": [
                {
                    "tool": action.tool,
                    "arguments": dict(action.arguments),
                    "approved": action.approved,
                }
                for action in self.actions
            ],
            "test_target": self.test_target,
        }
