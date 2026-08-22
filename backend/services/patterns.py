import json
import time

from services.db import get_connection


def init_pattern_db():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                id VARCHAR(128) PRIMARY KEY,
                openid VARCHAR(128) NOT NULL,
                data_json LONGTEXT NOT NULL,
                created_at BIGINT NOT NULL
            )
            """
        )
        try:
            connection.execute(
                "CREATE INDEX idx_patterns_openid ON patterns(openid)"
            )
        except Exception:
            pass  # index already exists
        connection.commit()


def save_pattern(openid, pattern):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO patterns (id, openid, data_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (pattern["id"], openid, json.dumps(pattern, ensure_ascii=False), int(time.time())),
        )
        connection.commit()


def get_pattern_for_user(openid, pattern_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT data_json FROM patterns WHERE id = ? AND openid = ?",
            (pattern_id, openid),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["data_json"])


def count_patterns():
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM patterns").fetchone()
    return row["total"]
