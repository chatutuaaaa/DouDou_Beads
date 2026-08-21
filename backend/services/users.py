import hashlib
import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                openid TEXT PRIMARY KEY,
                session_key TEXT,
                unionid TEXT,
                nickname TEXT,
                avatar_url TEXT,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                login_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        ensure_column(connection, "users", "nickname", "TEXT")
        ensure_column(connection, "users", "avatar_url", "TEXT")
        connection.commit()


def login_by_code(code, profile=None):
    appid = os.environ.get("WECHAT_APPID")
    secret = os.environ.get("WECHAT_SECRET")

    if appid and secret:
        session = fetch_wechat_session(appid, secret, code)
        openid = session["openid"]
        session_key = session.get("session_key")
        unionid = session.get("unionid")
        is_mock = False
    else:
        openid = f"dev_{hashlib.sha256(code.encode('utf-8')).hexdigest()[:24]}"
        session_key = None
        unionid = None
        is_mock = True

    user = upsert_user(openid, session_key, unionid, profile or {})
    return {**user, "isMock": is_mock}


def fetch_wechat_session(appid, secret, code):
    params = urllib.parse.urlencode({
        "appid": appid,
        "secret": secret,
        "js_code": code,
        "grant_type": "authorization_code"
    })
    url = f"https://api.weixin.qq.com/sns/jscode2session?{params}"

    with urllib.request.urlopen(url, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "openid" not in payload:
        message = payload.get("errmsg", "微信登录失败")
        raise ValueError(message)

    return payload


def upsert_user(openid, session_key, unionid, profile):
    now = int(time.time())
    nickname = clean_text(profile.get("nickname"))
    avatar_url = clean_text(profile.get("avatarUrl"))

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT openid, first_seen, login_count, nickname, avatar_url FROM users WHERE openid = ?",
            (openid,)
        ).fetchone()

        if existing:
            nickname = nickname or existing["nickname"]
            avatar_url = avatar_url or existing["avatar_url"]
            connection.execute(
                """
                UPDATE users
                SET session_key = ?, unionid = ?, nickname = ?, avatar_url = ?, last_seen = ?, login_count = login_count + 1
                WHERE openid = ?
                """,
                (session_key, unionid, nickname, avatar_url, now, openid)
            )
            first_seen = existing["first_seen"]
            login_count = existing["login_count"] + 1
        else:
            connection.execute(
                """
                INSERT INTO users (openid, session_key, unionid, nickname, avatar_url, first_seen, last_seen, login_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (openid, session_key, unionid, nickname, avatar_url, now, now)
            )
            first_seen = now
            login_count = 1

        connection.commit()

    return {
        "openid": openid,
        "openidMasked": mask_openid(openid),
        "nickname": nickname or "拼豆用户",
        "avatarUrl": avatar_url or "",
        "firstSeen": first_seen,
        "lastSeen": now,
        "loginCount": login_count
    }


def get_user(openid):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT openid, nickname, avatar_url, first_seen, last_seen, login_count FROM users WHERE openid = ?",
            (openid,)
        ).fetchone()

    if not row:
        return None

    return {
        "openid": row["openid"],
        "openidMasked": mask_openid(row["openid"]),
        "nickname": row["nickname"] or "拼豆用户",
        "avatarUrl": row["avatar_url"] or "",
        "firstSeen": row["first_seen"],
        "lastSeen": row["last_seen"],
        "loginCount": row["login_count"]
    }


def update_user_profile(openid, profile):
    nickname = clean_text(profile.get("nickname"))
    avatar_url = clean_text(profile.get("avatarUrl"))

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT nickname, avatar_url FROM users WHERE openid = ?",
            (openid,)
        ).fetchone()
        if not existing:
            return None

        nickname = nickname or existing["nickname"]
        avatar_url = avatar_url or existing["avatar_url"]
        connection.execute(
            "UPDATE users SET nickname = ?, avatar_url = ?, last_seen = ? WHERE openid = ?",
            (nickname, avatar_url, int(time.time()), openid)
        )
        connection.commit()

    return get_user(openid)


def get_user_stats():
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()

    return {"totalUsers": row["total"]}


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_column(connection, table, column, column_type):
    columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def clean_text(value):
    if not value:
        return ""

    return str(value).strip()[:256]


def mask_openid(openid):
    if len(openid) <= 12:
        return openid

    return f"{openid[:6]}...{openid[-4:]}"
