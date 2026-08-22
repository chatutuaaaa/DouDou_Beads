import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

from services.db import ensure_column, get_connection

DEFAULT_NICKNAME = "\u8c46\u8c46\u56fe\u7528\u6237"


def init_db():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                openid VARCHAR(128) PRIMARY KEY,
                session_key VARCHAR(255),
                unionid VARCHAR(128),
                nickname VARCHAR(255),
                avatar_url VARCHAR(512),
                first_seen BIGINT NOT NULL,
                last_seen BIGINT NOT NULL,
                login_count INT NOT NULL DEFAULT 0
            )
            """
        )
        ensure_column(connection, "users", "nickname", "VARCHAR(255)")
        ensure_column(connection, "users", "avatar_url", "VARCHAR(512)")
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
        openid = "dev_" + hashlib.sha256(code.encode("utf-8")).hexdigest()[:24]
        session_key = None
        unionid = None
        is_mock = True

    user = upsert_user(openid, session_key, unionid, profile or {})
    return {**user, "isMock": is_mock}


def ensure_user(openid, profile=None):
    """Upsert a cloud-authenticated user from X-WX-OPENID without a wx code."""
    return upsert_user(openid, None, None, profile or {})


def fetch_wechat_session(appid, secret, code):
    params = urllib.parse.urlencode({
        "appid": appid,
        "secret": secret,
        "js_code": code,
        "grant_type": "authorization_code",
    })
    url = f"https://api.weixin.qq.com/sns/jscode2session?{params}"

    with urllib.request.urlopen(url, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "openid" not in payload:
        raise ValueError(payload.get("errmsg", "\u5fae\u4fe1\u767b\u5f55\u5931\u8d25"))

    return payload


def upsert_user(openid, session_key, unionid, profile):
    now = int(time.time())
    nickname = clean_text(profile.get("nickname"))
    avatar_url = clean_text(profile.get("avatarUrl"))

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT openid, first_seen, login_count, nickname, avatar_url FROM users WHERE openid = ?",
            (openid,),
        ).fetchone()

        if existing:
            nickname = nickname or existing["nickname"]
            avatar_url = avatar_url or existing["avatar_url"]
            connection.execute(
                """
                UPDATE users
                SET session_key = ?, unionid = ?, nickname = ?, avatar_url = ?,
                    last_seen = ?, login_count = login_count + 1
                WHERE openid = ?
                """,
                (session_key, unionid, nickname, avatar_url, now, openid),
            )
            first_seen = existing["first_seen"]
            login_count = existing["login_count"] + 1
        else:
            connection.execute(
                """
                INSERT INTO users (openid, session_key, unionid, nickname, avatar_url,
                                   first_seen, last_seen, login_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (openid, session_key, unionid, nickname, avatar_url, now, now),
            )
            first_seen = now
            login_count = 1

        connection.commit()

    return build_user(openid, nickname, avatar_url, first_seen, now, login_count)


def get_user(openid):
    with get_connection() as connection:
        row = connection.execute(
            """SELECT openid, nickname, avatar_url, first_seen, last_seen, login_count
               FROM users WHERE openid = ?""",
            (openid,),
        ).fetchone()

    if not row:
        return None
    return build_user(row["openid"], row["nickname"], row["avatar_url"],
                      row["first_seen"], row["last_seen"], row["login_count"])


def build_user(openid, nickname, avatar_url, first_seen, last_seen, login_count):
    return {
        "openid": openid,
        "openidMasked": mask_openid(openid),
        "nickname": nickname or DEFAULT_NICKNAME,
        "avatarUrl": avatar_url or "",
        "firstSeen": first_seen,
        "lastSeen": last_seen,
        "loginCount": login_count,
    }


def update_user_profile(openid, profile):
    nickname = clean_text(profile.get("nickname"))
    avatar_url = clean_text(profile.get("avatarUrl"))

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT nickname, avatar_url FROM users WHERE openid = ?",
            (openid,),
        ).fetchone()
        if not existing:
            return None
        nickname = nickname or existing["nickname"]
        avatar_url = avatar_url or existing["avatar_url"]
        connection.execute(
            "UPDATE users SET nickname = ?, avatar_url = ?, last_seen = ? WHERE openid = ?",
            (nickname, avatar_url, int(time.time()), openid),
        )
        connection.commit()
    return get_user(openid)


def get_user_stats():
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
    return {"totalUsers": row["total"]}


def clean_text(value):
    if not value:
        return ""
    return str(value).strip()[:256]


def mask_openid(openid):
    if len(openid) <= 12:
        return openid
    return f"{openid[:6]}...{openid[-4:]}"
