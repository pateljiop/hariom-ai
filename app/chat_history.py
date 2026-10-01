import sqlite3
import time
from .config import APP_DIR


DB = APP_DIR / "chat_history.sqlite3"


class ChatHistoryStore:
    """Durable local chat history with full-text search over user/assistant messages."""

    def __init__(self, db_path=DB):
        self.db = db_path
        self._init()

    def _init(self):
        self.db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS chat_messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "conversation_id TEXT NOT NULL,"
                "role TEXT NOT NULL,"
                "content TEXT NOT NULL,"
                "created REAL NOT NULL)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_created "
                "ON chat_messages(created DESC)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_conversation "
                "ON chat_messages(conversation_id, created)"
            )
            con.commit()

    def add(self, conversation_id, role, content):
        content = str(content or "").strip()
        if not content:
            return None
        with sqlite3.connect(self.db) as con:
            cur = con.execute(
                "INSERT INTO chat_messages(conversation_id,role,content,created) "
                "VALUES(?,?,?,?)",
                (str(conversation_id), str(role), content, time.time()),
            )
            con.commit()
            return cur.lastrowid

    def conversation(self, conversation_id):
        with sqlite3.connect(self.db) as con:
            rows = con.execute(
                "SELECT id,role,content,created FROM chat_messages "
                "WHERE conversation_id=? ORDER BY created ASC",
                (str(conversation_id),),
            ).fetchall()
        return [{"id": r[0], "role": r[1], "content": r[2], "created": r[3]} for r in rows]

    def recent(self, limit=50):
        with sqlite3.connect(self.db) as con:
            rows = con.execute(
                "SELECT conversation_id, role, content, created FROM chat_messages "
                "ORDER BY created DESC LIMIT ?",
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [{"conversation_id": r[0], "role": r[1], "content": r[2], "created": r[3]} for r in rows]

    def search(self, query, limit=100):
        query = str(query or "").strip()
        if not query:
            return self.recent(limit)
        pattern = "%" + query + "%"
        with sqlite3.connect(self.db) as con:
            rows = con.execute(
                "SELECT conversation_id, role, content, created FROM chat_messages "
                "WHERE content LIKE ? ORDER BY created DESC LIMIT ?",
                (pattern, max(1, min(int(limit), 500))),
            ).fetchall()
        return [{"conversation_id": r[0], "role": r[1], "content": r[2], "created": r[3]} for r in rows]
