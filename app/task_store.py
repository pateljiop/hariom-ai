"""SQLite persistence for task state and execution events."""
import json
import sqlite3
from pathlib import Path
from typing import Optional

from .task import Task, TaskStatus


class TaskStore:
    def __init__(self, path="data/tasks.sqlite3"):
        self.path = str(path)
        parent = Path(self.path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                )"""
            )

    def create(self, task: Task):
        if self.get(task.task_id) is not None:
            raise ValueError(f"Task already exists: {task.task_id}")
        self.save(task)
        return task

    def save(self, task: Task):
        payload = json.dumps(task.to_dict(), separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO tasks(task_id,payload,status,created_at,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(task_id) DO UPDATE SET
                     payload=excluded.payload,
                     status=excluded.status,
                     updated_at=excluded.updated_at""",
                (task.task_id, payload, task.status.value, task.created_at, task.updated_at),
            )
        return task

    def get(self, task_id: str) -> Optional[Task]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            return None
        return self._from_payload(row["payload"])

    def events(self, task_id: str):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM task_events WHERE task_id=? ORDER BY id ASC",
                (task_id,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def append_event(self, task_id: str, event: dict):
        if self.get(task_id) is None:
            raise KeyError(f"Unknown task: {task_id}")
        payload = json.dumps(event, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO task_events(task_id,timestamp,status,payload) VALUES(?,?,?,?)",
                (task_id, event.get("timestamp", ""), event.get("status", ""), payload),
            )

    @staticmethod
    def _from_payload(payload):
        data = json.loads(payload)
        data["status"] = TaskStatus(data["status"])
        data["risk_level"] = data.get("risk_level", "low")
        from .task import RiskLevel, TaskStep
        data["risk_level"] = RiskLevel(data["risk_level"])
        data["steps"] = tuple(
            TaskStep(
                step_id=item["step_id"],
                tool=item["tool"],
                arguments=item.get("arguments", {}),
                dependencies=tuple(item.get("dependencies", [])),
                expected_files=tuple(item.get("expected_files", [])),
                test_commands=tuple(item.get("test_commands", [])),
                risk_level=RiskLevel(item.get("risk_level", "low")),
                required_approvals=tuple(item.get("required_approvals", [])),
            )
            for item in data.get("steps", [])
        )
        for key in ("dependencies", "expected_files", "test_commands", "required_approvals"):
            data[key] = tuple(data.get(key, []))
        return Task(**data)
