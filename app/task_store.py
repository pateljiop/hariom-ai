"""SQLite persistence for tasks, events, and approval requests."""
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
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                timestamp TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS approval_requests (
                request_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, payload TEXT NOT NULL,
                created_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE)""")

    def create(self, task: Task):
        if self.get(task.task_id) is not None:
            raise ValueError(f"Task already exists: {task.task_id}")
        return self.save(task)

    def save(self, task: Task):
        payload = json.dumps(task.to_dict(), separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("""INSERT INTO tasks(task_id,payload,status,created_at,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET
                payload=excluded.payload,status=excluded.status,updated_at=excluded.updated_at""",
                (task.task_id, payload, task.status.value, task.created_at, task.updated_at))
        return task

    def list_tasks(self, statuses=None):
        """Return persisted tasks, optionally filtered by status."""
        allowed = None if statuses is None else {
            status.value if isinstance(status, TaskStatus) else str(status)
            for status in statuses
        }
        with self._connect() as conn:
            if allowed:
                placeholders = ",".join("?" for _ in allowed)
                rows = conn.execute(
                    f"SELECT payload FROM tasks WHERE status IN ({placeholders}) ORDER BY updated_at DESC",
                    tuple(sorted(allowed)),
                ).fetchall()
            else:
                rows = conn.execute("SELECT payload FROM tasks ORDER BY updated_at DESC").fetchall()
        return [self._from_payload(row["payload"]) for row in rows]

    def get(self, task_id):
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return None if row is None else self._from_payload(row["payload"])

    def events(self, task_id):
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM task_events WHERE task_id=? ORDER BY id ASC", (task_id,)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def append_event(self, task_id, event):
        if self.get(task_id) is None:
            raise KeyError(f"Unknown task: {task_id}")
        with self._connect() as conn:
            conn.execute("INSERT INTO task_events(task_id,timestamp,status,payload) VALUES(?,?,?,?)",
                         (task_id, event.get("timestamp", ""), event.get("status", ""), json.dumps(event, separators=(",", ":"))))

    def save_approval(self, request_id, payload, created_at, expires_at, status="pending"):
        with self._connect() as conn:
            conn.execute("""INSERT INTO approval_requests(request_id,task_id,payload,created_at,expires_at,status)
                VALUES(?,?,?,?,?,?) ON CONFLICT(request_id) DO UPDATE SET
                payload=excluded.payload,expires_at=excluded.expires_at,status=excluded.status""",
                (request_id, payload.get("task_id", ""), json.dumps(payload, separators=(",", ":")),
                 created_at, expires_at, status))

    def get_approval(self, request_id):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM approval_requests WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload"])
        payload.update({"created_at": row["created_at"], "expires_at": row["expires_at"], "status": row["status"]})
        return payload

    @staticmethod
    def _from_payload(payload):
        data = json.loads(payload)
        from .task import RiskLevel, TaskStep
        data["status"] = TaskStatus(data["status"])
        data["risk_level"] = RiskLevel(data.get("risk_level", "low"))
        data["steps"] = tuple(TaskStep(
            step_id=item["step_id"], tool=item["tool"], arguments=item.get("arguments", {}),
            dependencies=tuple(item.get("dependencies", [])), expected_files=tuple(item.get("expected_files", [])),
            test_commands=tuple(item.get("test_commands", [])), risk_level=RiskLevel(item.get("risk_level", "low")),
            required_approvals=tuple(item.get("required_approvals", []))
        ) for item in data.get("steps", []))
        for key in ("dependencies", "expected_files", "test_commands", "required_approvals"):
            data[key] = tuple(data.get(key, []))
        return Task(**data)
