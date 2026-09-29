import hashlib
import json
import sqlite3
import time

from .config import APP_DIR, CACHE_TTL_SECONDS

DB = APP_DIR / 'response_cache.sqlite3'

def _init():
    with sqlite3.connect(DB) as con:
        con.execute(
            'CREATE TABLE IF NOT EXISTS cache '
            '(key TEXT PRIMARY KEY, value TEXT NOT NULL, created REAL NOT NULL)'
        )
        con.commit()

def key_for(messages, model=''):
    raw = json.dumps(
        {'messages': messages, 'model': model},
        sort_keys=True, ensure_ascii=False, default=str
    )
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def get(key, ttl=CACHE_TTL_SECONDS):
    _init()
    with sqlite3.connect(DB) as con:
        row = con.execute(
            'SELECT value, created FROM cache WHERE key=?', (key,)
        ).fetchone()
    if not row:
        return None
    if time.time() - row[1] > ttl:
        delete(key)
        return None
    return json.loads(row[0])

def put(key, value):
    _init()
    with sqlite3.connect(DB) as con:
        con.execute(
            'INSERT OR REPLACE INTO cache(key,value,created) VALUES(?,?,?)',
            (key, json.dumps(value, ensure_ascii=False), time.time())
        )
        con.commit()

def delete(key):
    _init()
    with sqlite3.connect(DB) as con:
        con.execute('DELETE FROM cache WHERE key=?', (key,))
        con.commit()
