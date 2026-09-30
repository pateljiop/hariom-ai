from dataclasses import dataclass, field
from enum import Enum
import json
import time
from pathlib import Path


class TaskStatus(str, Enum):
    PLANNING = "planning"
    RUNNING = "running"
    VERIFYING = "verifying"
    WAITING_APPROVAL = "waiting_approval"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class TaskState:
    request: str
    status: TaskStatus = TaskStatus.PLANNING
    steps: list = field(default_factory=list)
    current_step: int = -1
    attempts: int = 0
    errors: list = field(default_factory=list)
    result: str = ""
    provider: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_step(self, description, tool=None, arguments=None):
        self.steps.append({
            "description": description,
            "tool": tool,
            "arguments": arguments or {},
            "status": "pending",
            "output": "",
        })
        self.updated_at = time.time()

    def start_step(self, index):
        self.current_step = index
        self.steps[index]["status"] = "running"
        self.updated_at = time.time()

    def finish_step(self, output=""):
        self.steps[self.current_step]["status"] = "completed"
        self.steps[self.current_step]["output"] = output
        self.updated_at = time.time()

    def fail_step(self, error):
        self.steps[self.current_step]["status"] = "failed"
        self.steps[self.current_step]["output"] = str(error)
        self.errors.append(str(error))
        self.updated_at = time.time()

    def to_dict(self):
        return {
            "request": self.request,
            "status": self.status.value,
            "steps": self.steps,
            "current_step": self.current_step,
            "attempts": self.attempts,
            "errors": self.errors,
            "result": self.result,
            "provider": self.provider,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data):
        state = cls(
            request=str(data.get("request", "")),
            status=TaskStatus(data.get("status", TaskStatus.PLANNING.value)),
            steps=list(data.get("steps") or []),
            current_step=int(data.get("current_step", -1)),
            attempts=int(data.get("attempts", 0)),
            errors=list(data.get("errors") or []),
            result=str(data.get("result", "")),
            provider=str(data.get("provider", "")),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )
        return state


class TaskCheckpointStore:
    """Small JSON checkpoint store so interrupted tasks can be resumed."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id):
        safe = "".join(c for c in str(task_id) if c.isalnum() or c in "-_")
        return self.root / (safe + ".json")

    def save(self, task_id, state):
        path = self._path(task_id)
        path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, task_id):
        path = self._path(task_id)
        if not path.exists():
            return None
        return TaskState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self):
        items = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items.append((path.stem, TaskState.from_dict(data)))
            except (OSError, ValueError, TypeError):
                continue
        return items

    def delete(self, task_id):
        path = self._path(task_id)
        if path.exists():
            path.unlink()
            return True
        return False
