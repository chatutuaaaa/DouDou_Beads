import json
import sqlite3
import time

from services.users import DB_PATH, DATA_DIR


def init_pattern_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                id TEXT PRIMARY KEY,
                openid TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_patterns_openid ON patterns(openid)"
        )
        connection.commit()


def save_pattern(openid, pattern):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO patterns (id, openid, data_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (pattern["id"], openid, json.dumps(pattern, ensure_ascii=False), int(time.time()))
        )
        connection.commit()


def get_pattern_for_user(openid, pattern_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT data_json FROM patterns WHERE id = ? AND openid = ?",
            (pattern_id, openid)
        ).fetchone()

    if not row:
        return None

    return json.loads(row["data_json"])


def count_patterns():
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM patterns").fetchone()

    return row["total"]


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection
