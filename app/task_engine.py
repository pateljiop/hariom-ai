from dataclasses import dataclass, field
from enum import Enum
import time

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
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_step(self, description, tool=None, arguments=None):
        self.steps.append({"description":description,"tool":tool,"arguments":arguments or {},"status":"pending","output":""})
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
