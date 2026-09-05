import base64
import binascii
import io
import os
import urllib.parse
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


from flask import Flask, jsonify, request, send_file

from services.comments import fetch_hot_comment
from services.generator import generate_pattern
from services.exporter import export_pattern
from services.patterns import (
    count_patterns,
    get_pattern,
    init_pattern_db,
    save_anonymous_pattern,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.json.ensure_ascii = False
init_pattern_db()


@app.after_request
def add_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Admin-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/", methods=["GET"])
def root():
    return success({"status": "ok", "service": "doudoutu"})


@app.route("/__tcb_probe__", methods=["GET"])
def tcb_probe():
    return "ok", 200


@app.route("/api/health", methods=["GET"])
def health():
    return success({"status": "ok"})


@app.route("/api/hot-comment", methods=["GET"])
def hot_comment():
    try:
        return success({"comment": fetch_hot_comment()})
    except Exception:
        app.logger.exception("fetch hot comment failed")
        return failure("热评获取失败，请稍后重试", 500)


@app.route("/api/admin/stats", methods=["GET"])
def stats():
    admin_token = os.environ.get("ADMIN_TOKEN")
    if admin_token and request.headers.get("X-Admin-Token") != admin_token:
        return failure("无权限查看统计", 403)

    return success({"totalPatterns": count_patterns()})


@app.route("/api/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return success({})

    image_stream = None
    if request.is_json:
        body = request.get_json(silent=True) or {}
        image_raw = body.get("image") or ""
        image_b64 = image_raw.split(",")[-1] if image_raw else ""
        image_url = (body.get("imageUrl") or "").strip()
        if not image_b64 and not image_url:
            return failure("请上传图片", 400)
        try:
            if image_url:
                image_stream = download_remote_image(image_url)
            else:
                image_stream = io.BytesIO(base64.b64decode(image_b64, validate=True))
        except (binascii.Error, ValueError) as error:
            return failure(str(error) if str(error) else "图片数据无效", 400)
        width_default = body.get("width", 29)
        height_default = body.get("height", 29)
        max_colors_default = body.get("max_colors", 12)
        mode_default = body.get("mode", "clean")
        palette_default = body.get("palette", "mard_221")
    else:
        image = request.files.get("image")
        if not image:
            return failure("请上传图片", 400)
        image_stream = image.stream
        width_default = height_default = max_colors_default = None
        mode_default = "clean"
        palette_default = "mard_221"

    try:
        width = parse_int("width", width_default if width_default is not None else 29, 8, 120)
        height = parse_int("height", height_default if height_default is not None else 29, 8, 120)
        max_colors = parse_int("max_colors", max_colors_default if max_colors_default is not None else 12, 2, 48)
        mode = (mode_default if request.is_json else request.form.get("mode")) or "clean"
        palette = (palette_default if request.is_json else request.form.get("palette")) or "mard_221"

        data = generate_pattern(image_stream, width, height, max_colors, mode, palette)
        save_anonymous_pattern(data)
        return success(data)
    except ValueError as error:
        return failure(str(error), 400)
    except Exception:
        app.logger.exception("generate pattern failed")
        return failure("图片处理失败，请换一张图片再试", 500)


@app.route("/api/patterns/<pattern_id>/export", methods=["GET", "OPTIONS"])
def export(pattern_id):
    if request.method == "OPTIONS":
        return success({})

    file_format = request.args.get("format", "png").lower()
    if file_format not in ("png", "pdf"):
        return failure("导出格式仅支持 png 或 pdf", 400)

    pattern = get_pattern(pattern_id)
    if not pattern:
        return failure("图纸不存在或无权访问", 404)

    buffer, mime_type, filename = export_pattern(pattern, file_format)
    return send_file(buffer, mimetype=mime_type, as_attachment=True, download_name=filename)


@app.route("/api/patterns/<pattern_id>/export-base64", methods=["GET", "OPTIONS"])
def export_base64(pattern_id):
    if request.method == "OPTIONS":
        return success({})
    file_format = request.args.get("format", "png").lower()
    if file_format not in ("png", "pdf"):
        return failure("导出格式仅支持 png 或 pdf", 400)
    pattern = get_pattern(pattern_id)
    if not pattern:
        return failure("图纸不存在或无权访问", 404)
    buffer, mime_type, filename = export_pattern(pattern, file_format)
    return success({
        "filename": filename,
        "mimeType": mime_type,
        "dataBase64": base64.b64encode(buffer.getvalue()).decode("ascii"),
    })


def download_remote_image(image_url):
    parsed = urllib.parse.urlparse(image_url)
    if parsed.scheme != "https":
        raise ValueError("图片链接必须是 HTTPS")

    try:
        remote_request = urllib.request.Request(
            image_url,
            headers={"User-Agent": "DouDouTu/1.0"},
        )
        with urllib.request.urlopen(remote_request, timeout=12) as response:
            content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
            if content_type and not (content_type.startswith("image/") or content_type == "application/octet-stream"):
                raise ValueError("图片链接不是有效图片")

            max_size = app.config["MAX_CONTENT_LENGTH"]
            data = response.read(max_size + 1)
            if len(data) > max_size:
                raise ValueError("图片不能超过 8MB")
            if not data:
                raise ValueError("图片数据为空")
            return io.BytesIO(data)
    except ValueError:
        raise
    except Exception as error:
        app.logger.warning("download remote image failed: %s", error)
        raise ValueError("图片链接读取失败")


def parse_int(name, default, min_value, max_value):
    if request.is_json:
        raw_value = (request.get_json(silent=True) or {}).get(name, default)
    else:
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
