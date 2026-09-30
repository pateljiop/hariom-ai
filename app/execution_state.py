"""Execution state and bounded retry tracking."""
from dataclasses import dataclass, field
from datetime import datetime, timezone


STEP_PENDING = "pending"
STEP_RUNNING = "running"
STEP_SUCCEEDED = "succeeded"
STEP_FAILED = "failed"
STEP_SKIPPED = "skipped"


@dataclass
class ExecutionState:
    task_id: str
    stage: str = "created"
    attempts: int = 0
    max_attempts: int = 2
    events: list = field(default_factory=list)
    result: dict = field(default_factory=dict)
    steps: dict = field(default_factory=dict)

    def transition(self, stage, **data):
        self.stage = stage
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), "stage": stage, **data}
        self.events.append(event)
        return event

    def ensure_steps(self, actions):
        for index, action in enumerate(actions):
            step_id = action.step_id or f"step-{index + 1}"
            self.steps.setdefault(step_id, {
                "step_id": step_id, "status": STEP_PENDING, "attempts": 0,
                "result": None, "error": None,
            })

    def update_step(self, step_id, status, **data):
        record = self.steps.setdefault(step_id, {
            "step_id": step_id, "status": STEP_PENDING, "attempts": 0,
            "result": None, "error": None,
        })
        record["status"] = status
        record.update(data)
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(record)

    def step_is_succeeded(self, step_id):
        return self.steps.get(step_id, {}).get("status") == STEP_SUCCEEDED

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
            "task_id": self.task_id, "stage": self.stage, "attempts": self.attempts,
            "max_attempts": self.max_attempts, "events": list(self.events),
            "result": dict(self.result),
            "steps": {key: dict(value) for key, value in self.steps.items()},
        }
