"""Task domain model for persistent agent execution."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class TaskStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    TESTING = "testing"
    REPAIRING = "repairing"
    FAILED = "failed"
    CANCELLED = "cancelled"
    AWAITING_COMMIT_APPROVAL = "awaiting_commit_approval"
    COMMITTING = "committing"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    TIMED_OUT = "timed_out"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TaskStep:
    step_id: str
    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    dependencies: tuple = ()
    expected_files: tuple = ()
    test_commands: tuple = ()
    risk_level: RiskLevel = RiskLevel.LOW
    required_approvals: tuple = ()


@dataclass
class Task:
    task_id: str
    user_request: str
    objective: str
    status: TaskStatus = TaskStatus.CREATED
    steps: tuple = ()
    dependencies: tuple = ()
    expected_files: tuple = ()
    test_commands: tuple = ()
    risk_level: RiskLevel = RiskLevel.LOW
    required_approvals: tuple = ()
    rollback_strategy: str = "none"
    max_retries: int = 2
    plan: Optional[Dict[str, Any]] = None
    result: Dict[str, Any] = field(default_factory=dict)
    events: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string.")
        if not isinstance(self.user_request, str) or not self.user_request.strip():
            raise ValueError("user_request must be a non-empty string.")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be a non-empty string.")
        if not isinstance(self.status, TaskStatus):
            self.status = TaskStatus(self.status)
        if not isinstance(self.risk_level, RiskLevel):
            self.risk_level = RiskLevel(self.risk_level)
        if not isinstance(self.max_retries, int) or isinstance(self.max_retries, bool):
            raise ValueError("max_retries must be an integer.")
        if not 0 <= self.max_retries <= 10:
            raise ValueError("max_retries must be between 0 and 10.")
        if not isinstance(self.rollback_strategy, str) or not self.rollback_strategy.strip():
            raise ValueError("rollback_strategy must be a non-empty string.")

    _ALLOWED_TRANSITIONS = {
        TaskStatus.CREATED: {TaskStatus.PLANNING, TaskStatus.CANCELLED},
        TaskStatus.PLANNING: {TaskStatus.VALIDATING, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.VALIDATING: {TaskStatus.AWAITING_APPROVAL, TaskStatus.APPROVED, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.AWAITING_APPROVAL: {TaskStatus.APPROVED, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.APPROVED: {TaskStatus.EXECUTING, TaskStatus.CANCELLED},
        TaskStatus.EXECUTING: {TaskStatus.TESTING, TaskStatus.FAILED, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED},
        TaskStatus.TESTING: {TaskStatus.REPAIRING, TaskStatus.AWAITING_COMMIT_APPROVAL, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED},
        TaskStatus.REPAIRING: {TaskStatus.TESTING, TaskStatus.FAILED, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED},
        TaskStatus.AWAITING_COMMIT_APPROVAL: {TaskStatus.COMMITTING, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.COMMITTING: {TaskStatus.COMPLETED, TaskStatus.ROLLED_BACK, TaskStatus.FAILED, TaskStatus.TIMED_OUT},
        TaskStatus.FAILED: {TaskStatus.REPAIRING, TaskStatus.CANCELLED},
        TaskStatus.TIMED_OUT: {TaskStatus.REPAIRING, TaskStatus.CANCELLED},
        TaskStatus.CANCELLED: set(),
        TaskStatus.COMPLETED: set(),
        TaskStatus.ROLLED_BACK: set(),
    }

    def transition(self, status, **data):
        status = status if isinstance(status, TaskStatus) else TaskStatus(status)
        if status == self.status:
            raise ValueError(f"Task is already in status '{status.value}'.")
        allowed = self._ALLOWED_TRANSITIONS.get(self.status, set())
        if status not in allowed:
            raise ValueError(
                f"Invalid task transition: '{self.status.value}' -> '{status.value}'."
            )
        now = datetime.now(timezone.utc).isoformat()
        event = {"timestamp": now, "status": status.value, **data}
        self.status = status
        self.updated_at = now
        self.events.append(event)
        return event

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "user_request": self.user_request,
            "objective": self.objective,
            "status": self.status.value,
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
            "risk_level": self.risk_level.value,
            "required_approvals": list(self.required_approvals),
            "rollback_strategy": self.rollback_strategy,
            "max_retries": self.max_retries,
            "plan": self.plan,
            "result": self.result,
            "events": list(self.events),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
