import sqlite3
import time
from .config import APP_DIR

DB = APP_DIR / "memory.sqlite3"


class MemoryStore:
    """Local durable memory with categories, tags, confidence and importance."""

    VALID_KINDS = {"fact", "preference", "project", "routine", "context", "task"}

    def __init__(self, db_path=DB):
        self.db = db_path
        self._init()

    def _init(self):
        self.db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS memories "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, "
                "content TEXT NOT NULL, tags TEXT DEFAULT '', confidence REAL DEFAULT 1.0, "
                "importance INTEGER DEFAULT 1, created REAL NOT NULL, updated REAL NOT NULL)"
            )
            columns = {row[1] for row in con.execute("PRAGMA table_info(memories)")}
            if "confidence" not in columns:
                con.execute("ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 1.0")
            if "importance" not in columns:
                con.execute("ALTER TABLE memories ADD COLUMN importance INTEGER DEFAULT 1")
            con.execute("CREATE INDEX IF NOT EXISTS idx_memories_kind_updated ON memories(kind, updated DESC)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC, updated DESC)")
            con.commit()

    def remember(self, content, kind="fact", tags="", confidence=1.0, importance=1):
        content = str(content).strip()
        kind = str(kind).strip().lower()
        if not content:
            raise ValueError("memory content is required")
        if kind not in self.VALID_KINDS:
            raise ValueError("unsupported memory kind: " + kind)
        now = time.time()
        with sqlite3.connect(self.db) as con:
            cur = con.execute(
                "INSERT INTO memories(kind,content,tags,confidence,importance,created,updated) "
                "VALUES(?,?,?,?,?,?,?)",
                (kind, content, str(tags), max(0.0, min(float(confidence), 1.0)),
                 max(1, min(int(importance), 5)), now, now),
            )
            con.commit()
            return cur.lastrowid

    def search(self, query, limit=8, kind=None):
        text = str(query).strip()
        terms = [x for x in text.split() if x][:8]
        clauses, params = [], []
        if terms:
            for term in terms:
                q = "%" + term + "%"
                clauses.append("(content LIKE ? OR tags LIKE ?)")
                params.extend([q, q])
        else:
            clauses.append("1=1")
        if kind:
            clauses.append("kind=?")
            params.append(str(kind))
        params.append(max(1, min(int(limit), 100)))
        sql = (
            "SELECT id,kind,content,tags,confidence,importance,updated "
            "FROM memories WHERE " + " OR ".join(clauses) +
            " ORDER BY importance DESC, updated DESC LIMIT ?"
        )
        with sqlite3.connect(self.db) as con:
            rows = con.execute(sql, params).fetchall()
        return [self._row(r) for r in rows]

    def recent(self, limit=10, kind=None):
        params = []
        where = ""
        if kind:
            where = " WHERE kind=?"
            params.append(str(kind))
        params.append(max(1, min(int(limit), 100)))
        with sqlite3.connect(self.db) as con:
            rows = con.execute(
                "SELECT id,kind,content,tags,confidence,importance,updated "
                "FROM memories" + where + " ORDER BY updated DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row(r) for r in rows]

    def important(self, limit=20):
        params = [max(1, min(int(limit), 100))]
        with sqlite3.connect(self.db) as con:
            rows = con.execute(
                "SELECT id,kind,content,tags,confidence,importance,updated "
                "FROM memories ORDER BY importance DESC, updated DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row(r) for r in rows]

    def update(self, memory_id, content=None, tags=None, confidence=None, importance=None):
        fields, params = [], []
        if content is not None:
            fields.append("content=?"); params.append(str(content).strip())
        if tags is not None:
            fields.append("tags=?"); params.append(str(tags))
        if confidence is not None:
            fields.append("confidence=?"); params.append(max(0.0, min(float(confidence), 1.0)))
        if importance is not None:
            fields.append("importance=?"); params.append(max(1, min(int(importance), 5)))
        if not fields:
            return False
        fields.append("updated=?"); params.append(time.time())
        params.append(int(memory_id))
        with sqlite3.connect(self.db) as con:
            cur = con.execute("UPDATE memories SET " + ", ".join(fields) + " WHERE id=?", params)
            con.commit()
            return cur.rowcount > 0

    def forget(self, memory_id):
        with sqlite3.connect(self.db) as con:
            cur = con.execute("DELETE FROM memories WHERE id=?", (int(memory_id),))
            con.commit()
            return cur.rowcount > 0

    @staticmethod
    def _row(row):
        return {
            "id": row[0], "kind": row[1], "content": row[2], "tags": row[3],
            "confidence": row[4], "importance": row[5], "updated": row[6],
        }
