"""Execution state and bounded retry tracking."""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ExecutionState:
    task_id: str
    stage: str = "created"
    attempts: int = 0
    max_attempts: int = 3
    events: list = field(default_factory=list)
    result: dict = field(default_factory=dict)

    def transition(self, stage, **data):
        self.stage = stage
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            **data,
        }
        self.events.append(event)
        return event

    def can_retry(self):
        return self.attempts < self.max_attempts

    def record_attempt(self):
        if not self.can_retry():
            return False
        self.attempts += 1
        self.transition("retry", attempt=self.attempts)
        return True

    def snapshot(self):
        return {
            "task_id": self.task_id,
            "stage": self.stage,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "events": list(self.events),
            "result": dict(self.result),
        }
