import os
from functools import wraps

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


from flask import Flask, jsonify, request, send_file
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from services.generator import generate_pattern
from services.exporter import export_pattern
from services.patterns import count_patterns, get_pattern_for_user, init_pattern_db, save_pattern
from services.users import get_user, get_user_stats, init_db, login_by_code, update_user_profile
from services.guests import (
    consume_trial,
    create_guest,
    get_guest,
    init_guest_db,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "doudoutu-dev-secret")
app.json.ensure_ascii = False
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
init_db()
init_pattern_db()
init_guest_db()


@app.after_request
def add_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Admin-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/api/health", methods=["GET"])
def health():
    return success({"status": "ok"})


@app.route("/api/auth/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return success({})

    body = request.get_json(silent=True) or {}
    code = body.get("code")
    if not code:
        return failure("缺少微信登录 code", 400)

    try:
        profile = {
            "nickname": body.get("nickname", ""),
            "avatarUrl": body.get("avatarUrl", "")
        }
        user = login_by_code(code, profile)
        token = create_token(user["openid"])
        return success({"token": token, "user": public_user(user)})
    except ValueError as error:
        return failure(str(error), 400)
    except Exception:
        app.logger.exception("wechat login failed")
        return failure("微信登录失败，请稍后重试", 500)

@app.route("/api/auth/guest", methods=["POST", "OPTIONS"])
def guest_login():
    if request.method == "OPTIONS":
        return success({})
    guest = create_guest()
    token = create_guest_token(guest["guestId"])
    return success({"token": token, "user": public_auth_user(guest)})


def require_login(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return view(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "", 1).strip()
        if not token:
            return failure("请先登录", 401)

        try:
            payload = read_token(token)
        except SignatureExpired:
            return failure("登录已过期，请重新登录", 401)
        except BadSignature:
            return failure("登录状态无效，请重新登录", 401)

        if payload.get("gid"):
            guest = get_guest(payload.get("gid"))
            if not guest:
                return failure("试用已失效，请重新登录", 401)
            request.current_user = guest
            return view(*args, **kwargs)

        user = get_user(payload.get("openid"))
        if not user:
            return failure("用户不存在，请重新登录", 401)

        request.current_user = user
        return view(*args, **kwargs)

    return wrapper


@app.route("/api/auth/me", methods=["GET"])
@require_login
def me():
    return success({"user": public_auth_user(request.current_user)})


@app.route("/api/auth/profile", methods=["POST", "OPTIONS"])
@require_login
def profile():
    if request.method == "OPTIONS":
        return success({})

    body = request.get_json(silent=True) or {}
    user = update_user_profile(request.current_user["openid"], body)
    if not user:
        return failure("用户不存在，请重新登录", 401)

    return success({"user": public_user(user)})


@app.route("/api/admin/stats", methods=["GET"])
def stats():
    admin_token = os.environ.get("ADMIN_TOKEN")
    if admin_token and request.headers.get("X-Admin-Token") != admin_token:
        return failure("无权限查看统计", 403)

    data = get_user_stats()
    data["totalPatterns"] = count_patterns()
    return success(data)


@app.route("/api/generate", methods=["POST", "OPTIONS"])
@require_login
def generate():
    if request.method == "OPTIONS":
        return success({})

    image = request.files.get("image")
    if not image:
        return failure("请上传图片", 400)

    try:
        width = get_int("width", 29, 8, 120)
        height = get_int("height", 29, 8, 120)
        max_colors = get_int("max_colors", 12, 2, 32)
        mode = request.form.get("mode", "clean")
        palette = request.form.get("palette", "artkal_s")
        current_user = request.current_user
        remaining = None
        if current_user.get("isGuest"):
            allowed, remaining = consume_trial(current_user["guestId"])
            if not allowed:
                return failure("试用次数已用完，请登录后继续使用", 403)

        data = generate_pattern(image.stream, width, height, max_colors, mode, palette)
        save_pattern(current_user["openid"], data)
        if remaining is not None:
            data["trialRemaining"] = remaining
        return success(data)
    except ValueError as error:
        return failure(str(error), 400)
    except Exception:
        app.logger.exception("generate pattern failed")
        return failure("图片处理失败，请换一张图片再试", 500)


@app.route("/api/patterns/<pattern_id>/export", methods=["GET", "OPTIONS"])
@require_login
def export(pattern_id):
    if request.method == "OPTIONS":
        return success({})

    file_format = request.args.get("format", "png").lower()
    if file_format not in ("png", "pdf"):
        return failure("导出格式仅支持 png 或 pdf", 400)

    pattern = get_pattern_for_user(request.current_user["openid"], pattern_id)
    if not pattern:
        return failure("图纸不存在或无权访问", 404)

    buffer, mime_type, filename = export_pattern(pattern, file_format)
    return send_file(buffer, mimetype=mime_type, as_attachment=True, download_name=filename)


def get_int(name, default, min_value, max_value):
    raw_value = request.form.get(name, default)

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} 参数不合法")

    if value < min_value or value > max_value:
        raise ValueError(f"{name} 必须在 {min_value}-{max_value} 之间")

    return value


def success(data):
    return jsonify({"code": 0, "message": "success", "data": data})


def failure(message, status_code):
    return jsonify({"code": status_code, "message": message, "data": None}), status_code


def create_token(openid):
    return serializer.dumps({"openid": openid}, salt="wechat-login")

def create_guest_token(guest_id):
    return serializer.dumps({"gid": guest_id}, salt="wechat-login")


def read_token(token):
    return serializer.loads(token, salt="wechat-login", max_age=30 * 24 * 60 * 60)


def public_auth_user(user):
    if user.get("isGuest"):
        return {
            "openidMasked": user["openidMasked"],
            "nickname": user.get("nickname", "试用用户"),
            "avatarUrl": user.get("avatarUrl", ""),
            "firstSeen": user["firstSeen"],
            "lastSeen": user["lastSeen"],
            "loginCount": 0,
            "isGuest": True,
            "trialUsed": user["trialUsed"],
            "trialLimit": user["trialLimit"],
            "trialRemaining": user["trialRemaining"],
        }
    return public_user(user)


def public_user(user):
    return {
        "openidMasked": user["openidMasked"],
        "nickname": user.get("nickname", "豆豆图用户"),
        "avatarUrl": user.get("avatarUrl", ""),
        "firstSeen": user["firstSeen"],
        "lastSeen": user["lastSeen"],
        "loginCount": user["loginCount"],
        "isMock": user.get("isMock", False)
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
