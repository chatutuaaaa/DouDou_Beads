from collections import Counter
from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

from PIL import Image, ImageEnhance, ImageOps

from services.palettes import PALETTES

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_LANCZOS = Image.LANCZOS

try:
    ADAPTIVE_PALETTE = Image.Palette.ADAPTIVE
except AttributeError:
    ADAPTIVE_PALETTE = Image.ADAPTIVE

try:
    DITHER_NONE = Image.Dither.NONE
except AttributeError:
    DITHER_NONE = Image.NONE

SYMBOLS = list("ABCDEFGHJKLMNPQRSTUVWXYZ") + list("123456789") + ["α", "β", "γ", "△", "○", "□", "◇", "☆", "＋", "×", "#", "@", "%", "&"]
BOARD_SIZE = 29


def generate_pattern(image_file, width, height, max_colors, mode, palette_name):
    palette = PALETTES.get(palette_name)
    if not palette:
        raise ValueError("不支持的色卡")

    image = load_image(image_file)
    image = center_crop(image, width, height)
    image = apply_mode(image, mode)
    image = image.resize((width, height), RESAMPLE_LANCZOS)
    quantized = quantize_image(image, max_colors)
    selected_palette = pick_palette_colors(quantized, palette, max_colors)
    grid, counts = build_grid(quantized, selected_palette)
    palette_result = build_palette_result(selected_palette, counts)

    return {
        "id": uuid4().hex,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "width": width,
        "height": height,
        "totalBeads": width * height,
        "paletteName": palette_name,
        "mode": mode,
        "board": {
            "size": BOARD_SIZE,
            "columns": ceil(width / BOARD_SIZE),
            "rows": ceil(height / BOARD_SIZE),
            "count": ceil(width / BOARD_SIZE) * ceil(height / BOARD_SIZE)
        },
        "palette": palette_result,
        "grid": grid
    }


def load_image(image_file):
    image = Image.open(image_file)
    image = ImageOps.exif_transpose(image)

    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image.convert("RGBA"))

    return image.convert("RGB")


def center_crop(image, target_width, target_height):
    source_width, source_height = image.size
    target_ratio = target_width / target_height
    source_ratio = source_width / source_height

    if source_ratio > target_ratio:
        crop_width = int(source_height * target_ratio)
        left = (source_width - crop_width) // 2
        box = (left, 0, left + crop_width, source_height)
    else:
        crop_height = int(source_width / target_ratio)
        top = (source_height - crop_height) // 2
        box = (0, top, source_width, top + crop_height)

    return image.crop(box)


def apply_mode(image, mode):
    if mode == "clean":
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(1.18)
        image = ImageEnhance.Sharpness(image).enhance(1.2)
        return ImageEnhance.Color(image).enhance(1.08)

    if mode == "natural":
        image = ImageOps.autocontrast(image, cutoff=0.5)
        return ImageEnhance.Contrast(image).enhance(1.05)

    return image


def quantize_image(image, max_colors):
    colors = max(2, min(max_colors, 32))
    return image.convert("P", palette=ADAPTIVE_PALETTE, colors=colors, dither=DITHER_NONE).convert("RGB")


def pick_palette_colors(image, palette, max_colors):
    selected = []
    selected_ids = set()

    for rgb, _count in Counter(image.getdata()).most_common(max_colors * 3):
        color = nearest_color(rgb, palette)
        if color["id"] in selected_ids:
            continue

        selected.append(color)
        selected_ids.add(color["id"])

        if len(selected) >= max_colors:
            break

    if not selected:
        selected.append(palette[1])

    return selected


def build_grid(image, palette):
    counts = Counter()
    pixels = list(image.getdata())
    width, height = image.size
    grid = []

    for row_index in range(height):
        row = []
        for column_index in range(width):
            rgb = pixels[row_index * width + column_index]
            color = nearest_color(rgb, palette)
            color_id = color["id"]
            row.append(color_id)
            counts[color_id] += 1
        grid.append(row)

    return grid, counts


def build_palette_result(palette, counts):
    result = []

    for index, color in enumerate(palette):
        count = counts[color["id"]]
        if count <= 0:
            continue

        result.append({
            "id": color["id"],
            "name": color["name"],
            "rgb": color["rgb"],
            "hex": rgb_to_hex(color["rgb"]),
            "symbol": SYMBOLS[index] if index < len(SYMBOLS) else str(index + 1),
            "count": count,
            "suggestCount": ceil(count * 1.05)
        })

    return sorted(result, key=lambda item: item["count"], reverse=True)


def nearest_color(rgb, palette):
    return min(palette, key=lambda color: color_distance(rgb, color["rgb"]))


def color_distance(source, target):
    red = source[0] - target[0]
    green = source[1] - target[1]
    blue = source[2] - target[2]
    return red * red * 0.3 + green * green * 0.59 + blue * blue * 0.11


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])
