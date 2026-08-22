import sqlite3
import time
from uuid import uuid4

from services.users import DB_PATH, DATA_DIR

TRIAL_LIMIT = 3
GUEST_PREFIX = "guest_"


def init_guest_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS guests (
                guest_id TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                trial_used INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.commit()


def create_guest():
    guest_id = GUEST_PREFIX + uuid4().hex
    now = int(time.time())
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO guests (guest_id, created_at, last_seen, trial_used) VALUES (?, ?, ?, 0)",
            (guest_id, now, now),
        )
        connection.commit()
    return public_guest(guest_id, now, now, 0)


def get_guest(guest_id):
    if not guest_id or not guest_id.startswith(GUEST_PREFIX):
        return None
    with get_connection() as connection:
        row = connection.execute(
            "SELECT guest_id, created_at, last_seen, trial_used FROM guests WHERE guest_id = ?",
            (guest_id,),
        ).fetchone()
    if not row:
        return None
    return public_guest(row["guest_id"], row["created_at"], row["last_seen"], row["trial_used"])


def consume_trial(guest_id):
    """Atomically increment trial_used and return (allowed, remaining)."""
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE guests SET trial_used = trial_used + 1, last_seen = ? WHERE guest_id = ? AND trial_used < ?",
            (int(time.time()), guest_id, TRIAL_LIMIT),
        )
        allowed = cursor.rowcount > 0
        row = connection.execute(
            "SELECT trial_used FROM guests WHERE guest_id = ?",
            (guest_id,),
        ).fetchone()
        connection.commit()

    if row is None:
        return False, 0
    remaining = max(0, TRIAL_LIMIT - row["trial_used"])
    return allowed, remaining


def public_guest(guest_id, created_at, last_seen, trial_used):
    return {
        "guestId": guest_id,
        "openid": guest_id,
        "openidMasked": guest_id[:12] + "..." + guest_id[-4:],
        "nickname": "试用用户",
        "avatarUrl": "",
        "firstSeen": created_at,
        "lastSeen": last_seen,
        "loginCount": 0,
        "isGuest": True,
        "trialUsed": trial_used,
        "trialLimit": TRIAL_LIMIT,
        "trialRemaining": max(0, TRIAL_LIMIT - trial_used),
    }


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection
