"""Structured, backward-compatible task plan validation for agent execution."""
from dataclasses import dataclass
from typing import Any, Dict

from .task import RiskLevel, TaskStep
from .task_executor import TaskAction, TaskExecutionError


class PlanValidationError(TaskExecutionError):
    """Raised when an external task plan is malformed."""


@dataclass(frozen=True)
class TaskPlan:
    actions: tuple
    test_target: str = "tests"
    task_id: str = ""
    user_request: str = ""
    objective: str = ""
    steps: tuple = ()
    dependencies: tuple = ()
    expected_files: tuple = ()
    test_commands: tuple = ()
    risk_level: str = "low"
    required_approvals: tuple = ()
    rollback_strategy: str = "none"
    max_retries: int = 2

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise PlanValidationError("Plan must be an object.")
        raw_steps = payload.get("steps")
        raw_actions = payload.get("actions")
        if raw_steps is None:
            raw_steps = raw_actions
        if not isinstance(raw_steps, list) or not raw_steps:
            raise PlanValidationError("Plan steps/actions must be a non-empty list.")

        actions = []
        steps = []
        for index, raw in enumerate(raw_steps):
            if not isinstance(raw, dict):
                raise PlanValidationError(f"Step {index} must be an object.")
            tool = raw.get("tool")
            arguments = raw.get("arguments", {})
            approved = raw.get("approved", False)
            if not isinstance(tool, str) or not tool.strip():
                raise PlanValidationError(f"Step {index} has an invalid tool.")
            if not isinstance(arguments, dict):
                raise PlanValidationError(f"Step {index} arguments must be an object.")
            if not isinstance(approved, bool):
                raise PlanValidationError(f"Step {index} approved must be boolean.")
            step_id = raw.get("step_id", f"step-{index + 1}")
            if not isinstance(step_id, str) or not step_id.strip():
                raise PlanValidationError(f"Step {index} step_id must be a non-empty string.")
            def step_seq(name):
                value = raw.get(name, [])
                if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                    raise PlanValidationError(f"Step {index} {name} must be a list of non-empty strings.")
                return tuple(item.strip() for item in value)
            step_risk = raw.get("risk_level", payload.get("risk_level", "low"))
            if step_risk not in {"low", "medium", "high", "critical"}:
                raise PlanValidationError(f"Step {index} risk_level is invalid.")
            dependencies = step_seq("dependencies")
            actions.append(TaskAction(tool.strip(), arguments, approved, dependencies))
            steps.append(TaskStep(step_id.strip(), tool.strip(), arguments, step_seq("dependencies"), step_seq("expected_files"), step_seq("test_commands"), RiskLevel(step_risk), step_seq("required_approvals")))

        step_ids = [step.step_id for step in steps]
        if len(step_ids) != len(set(step_ids)):
            raise PlanValidationError("Step IDs must be unique.")
        step_id_set = set(step_ids)
        for step in steps:
            for dependency in step.dependencies:
                if dependency == step.step_id:
                    raise PlanValidationError(f"Step '{step.step_id}' cannot depend on itself.")
                if dependency not in step_id_set:
                    raise PlanValidationError(
                        f"Step '{step.step_id}' depends on unknown step '{dependency}'."
                    )

        visiting = set()
        visited = set()

        def visit(step_id):
            if step_id in visiting:
                raise PlanValidationError(f"Circular step dependency detected at '{step_id}'.")
            if step_id in visited:
                return
            visiting.add(step_id)
            current = steps[step_ids.index(step_id)]
            for dependency in current.dependencies:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_ids:
            visit(step_id)

        test_target = payload.get("test_target", "tests")
        if not isinstance(test_target, str) or not test_target.strip():
            raise PlanValidationError("test_target must be a non-empty string.")

        task_id = payload.get("task_id", "")
        user_request = payload.get("user_request", "")
        objective = payload.get("objective", "")
        for name, value in (("task_id", task_id), ("user_request", user_request), ("objective", objective)):
            if value and not isinstance(value, str):
                raise PlanValidationError(f"{name} must be a string.")
        risk_level = payload.get("risk_level", "low")
        if risk_level not in {"low", "medium", "high", "critical"}:
            raise PlanValidationError("risk_level must be low, medium, high, or critical.")
        max_retries = payload.get("max_retries", 2)
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or not 0 <= max_retries <= 10:
            raise PlanValidationError("max_retries must be an integer between 0 and 10.")

        def seq(name):
            value = payload.get(name, [])
            if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise PlanValidationError(f"{name} must be a list of non-empty strings.")
            return tuple(item.strip() for item in value)

        rollback = payload.get("rollback_strategy", "none")
        if not isinstance(rollback, str) or not rollback.strip():
            raise PlanValidationError("rollback_strategy must be a non-empty string.")

        return cls(
            tuple(actions), test_target.strip(),
            task_id.strip(), user_request.strip(), objective.strip(),
            tuple(steps), seq("dependencies"), seq("expected_files"), seq("test_commands"),
            risk_level, seq("required_approvals"), rollback.strip(), max_retries,
        )

    def to_dict(self):
        return {
            "actions": [
                {"tool": action.tool, "arguments": dict(action.arguments), "approved": action.approved}
                for action in self.actions
            ],
            "test_target": self.test_target,
            "task_id": self.task_id,
            "user_request": self.user_request,
            "objective": self.objective,
            "steps": [
                {
                    "step_id": step.step_id,
                    "tool": step.tool,
                    "arguments": dict(step.arguments),
                    "dependencies": list(step.dependencies),
                    "expected_files": list(step.expected_files),
                    "test_commands": list(step.test_commands),
                    "risk_level": step.risk_level.value,
                    "required_approvals": list(step.required_approvals),
                }
                for step in self.steps
            ],
            "dependencies": list(self.dependencies),
            "expected_files": list(self.expected_files),
            "test_commands": list(self.test_commands),
            "risk_level": self.risk_level,
            "required_approvals": list(self.required_approvals),
            "rollback_strategy": self.rollback_strategy,
            "max_retries": self.max_retries,
        }
