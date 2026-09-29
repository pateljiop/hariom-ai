import sqlite3
import time
from .config import APP_DIR

DB = APP_DIR / "memory.sqlite3"

class MemoryStore:
    """Local memory for useful facts, preferences and project notes."""
    def __init__(self, db_path=DB):
        self.db = db_path
        self._init()

    def _init(self):
        self.db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, content TEXT NOT NULL, tags TEXT DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_memories_kind_updated ON memories(kind, updated DESC)")
            con.commit()

    def remember(self, content, kind="fact", tags=""):
        content = str(content).strip()
        if not content:
            raise ValueError("memory content is required")
        now = time.time()
        with sqlite3.connect(self.db) as con:
            cur = con.execute("INSERT INTO memories(kind,content,tags,created,updated) VALUES(?,?,?,?,?)", (kind, content, tags, now, now))
            con.commit()
            return cur.lastrowid

    def search(self, query, limit=8):
        q = "%" + str(query).strip() + "%"
        with sqlite3.connect(self.db) as con:
            rows = con.execute("SELECT id,kind,content,tags,updated FROM memories WHERE content LIKE ? OR tags LIKE ? ORDER BY updated DESC LIMIT ?", (q, q, int(limit))).fetchall()
        return [{"id":r[0],"kind":r[1],"content":r[2],"tags":r[3],"updated":r[4]} for r in rows]

    def recent(self, limit=10):
        with sqlite3.connect(self.db) as con:
            rows = con.execute("SELECT id,kind,content,tags,updated FROM memories ORDER BY updated DESC LIMIT ?", (int(limit),)).fetchall()
        return [{"id":r[0],"kind":r[1],"content":r[2],"tags":r[3],"updated":r[4]} for r in rows]

    def forget(self, memory_id):
        with sqlite3.connect(self.db) as con:
            cur = con.execute("DELETE FROM memories WHERE id=?", (int(memory_id),))
            con.commit()
            return cur.rowcount > 0
