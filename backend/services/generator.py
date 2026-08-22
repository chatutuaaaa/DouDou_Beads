from collections import Counter
from datetime import datetime, timezone
from math import atan2, cbrt, ceil, cos, degrees, exp, radians, sin, sqrt
from uuid import uuid4

from PIL import Image, ImageEnhance, ImageOps

from services.palettes import PALETTES

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_LANCZOS = Image.LANCZOS

SYMBOLS = (
    list("ABCDEFGHJKLMNPQRSTUVWXYZ")
    + list("23456789")
    + ["#", "@", "%", "&", "+", "="]
)
BOARD_SIZE = 29


def generate_pattern(image_file, width, height, max_colors, mode, palette_name):
    palette = PALETTES.get(palette_name)
    if not palette:
        raise ValueError("不支持的色卡")

    image = load_image(image_file)
    image = center_crop(image, width, height)
    image = apply_mode(image, mode)
    image = image.resize((width, height), RESAMPLE_LANCZOS)

    dither = mode == "natural"
    grid, counts, selected_palette = map_image_to_palette(
        image, palette, max_colors, dither=dither
    )
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
            "count": ceil(width / BOARD_SIZE) * ceil(height / BOARD_SIZE),
        },
        "palette": palette_result,
        "grid": grid,
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
        image = ImageOps.autocontrast(image, cutoff=0.5)
        image = ImageEnhance.Contrast(image).enhance(1.08)
        return ImageEnhance.Sharpness(image).enhance(1.10)

    if mode == "natural":
        image = ImageOps.autocontrast(image, cutoff=0.2)
        return ImageEnhance.Contrast(image).enhance(1.03)

    return image


def map_image_to_palette(image, palette, max_colors, dither=False):
    """Map every pixel to bead colors.

    First pass maps against the full palette in CIE Lab space using
    CIEDE2000, keeps the most-used ``max_colors`` colors, then performs a
    second pass. With dithering enabled, Floyd-Steinberg error diffusion in
    Lab space smooths gradients and preserves fine detail.
    """
    palette_by_id = {color["id"]: color for color in palette}
    pixels = list(image.getdata())
    width, height = image.size

    full_lab = [(color, rgb_to_lab(color["rgb"])) for color in palette]
    first_grid = [
        min(full_lab, key=lambda item, lab=rgb_to_lab(pixel): color_distance(lab, item[1]))[0]["id"]
        for pixel in pixels
    ]

    counts = Counter(first_grid)
    selected_ids = [color_id for color_id, _count in counts.most_common(max_colors)]
    if not selected_ids:
        selected_ids = [palette[0]["id"]]

    selected = [palette_by_id[color_id] for color_id in selected_ids]
    selected_lab = [rgb_to_lab(color["rgb"]) for color in selected]

    if dither:
        grid = floyd_steinberg(pixels, selected, selected_lab, width, height)
    else:
        grid = [
            min(
                range(len(selected_lab)),
                key=lambda index, lab=rgb_to_lab(pixel): color_distance(lab, selected_lab[index]),
            )
            for pixel in pixels
        ]
        grid = [selected[index]["id"] for index in grid]

    counts = Counter(grid)
    ordered_ids = [color_id for color_id, _count in counts.most_common()]
    selected = [palette_by_id[color_id] for color_id in ordered_ids]

    rows = [grid[row * width:(row + 1) * width] for row in range(height)]
    return rows, counts, selected


def floyd_steinberg(pixels, selected_colors, selected_lab, width, height, strength=0.75):
    grid = [""] * (width * height)
    buffer = [list(rgb_to_lab(pixel)) for pixel in pixels]

    for y in range(height):
        for x in range(width):
            index = y * width + x
            current = buffer[index]
            nearest = min(
                range(len(selected_lab)),
                key=lambda candidate: color_distance(current, selected_lab[candidate]),
            )
            chosen = selected_lab[nearest]
            grid[index] = selected_colors[nearest]["id"]

            error = [
                (current[0] - chosen[0]) * strength,
                (current[1] - chosen[1]) * strength,
                (current[2] - chosen[2]) * strength,
            ]
            distribute(buffer, x + 1, y, width, height, error, 7.0 / 16.0)
            distribute(buffer, x - 1, y + 1, width, height, error, 3.0 / 16.0)
            distribute(buffer, x, y + 1, width, height, error, 5.0 / 16.0)
            distribute(buffer, x + 1, y + 1, width, height, error, 1.0 / 16.0)

    return grid


def distribute(buffer, x, y, width, height, error, weight):
    if x < 0 or x >= width or y < 0 or y >= height:
        return
    index = y * width + x
    buffer[index][0] += error[0] * weight
    buffer[index][1] += error[1] * weight
    buffer[index][2] += error[2] * weight


def build_palette_result(palette, counts):
    result = []

    for index, color in enumerate(palette):
        count = counts[color["id"]]
        if count <= 0:
            continue

        result.append(
            {
                "id": color["id"],
                "name": color["name"],
                "rgb": color["rgb"],
                "hex": rgb_to_hex(color["rgb"]),
                "symbol": SYMBOLS[index] if index < len(SYMBOLS) else str(index + 1),
                "count": count,
                "suggestCount": ceil(count * 1.05),
            }
        )

    return sorted(result, key=lambda item: item["count"], reverse=True)


def nearest_color(rgb, palette):
    lab = rgb_to_lab(rgb)
    return min(palette, key=lambda color: color_distance(lab, rgb_to_lab(color["rgb"])))


def color_distance(lab1, lab2):
    return ciede2000(lab1, lab2)


def ciede2000(lab1, lab2):
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    avg_l = (l1 + l2) / 2.0
    c1 = sqrt(a1 * a1 + b1 * b1)
    c2 = sqrt(a2 * a2 + b2 * b2)
    avg_c = (c1 + c2) / 2.0
    avg_c7 = avg_c ** 7
    g = 0.5 * (1.0 - sqrt(avg_c7 / (avg_c7 + 25.0 ** 7)))
    a1p = a1 * (1.0 + g)
    a2p = a2 * (1.0 + g)
    c1p = sqrt(a1p * a1p + b1 * b1)
    c2p = sqrt(a2p * a2p + b2 * b2)
    h1p = hue_degrees(b1, a1p)
    h2p = hue_degrees(b2, a2p)

    delta_lp = l2 - l1
    delta_cp = c2p - c1p
    if c1 * c2 == 0:
        delta_hp = 0.0
    elif abs(h2p - h1p) <= 180.0:
        delta_hp = h2p - h1p
    elif h2p - h1p > 180.0:
        delta_hp = h2p - h1p - 360.0
    else:
        delta_hp = h2p - h1p + 360.0
    delta_h = 2.0 * sqrt(c1p * c2p) * sin(radians(delta_hp / 2.0))

    avg_lp = (l1 + l2) / 2.0
    avg_cp = (c1p + c2p) / 2.0
    if c1p * c2p == 0:
        avg_hp = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        avg_hp = (h1p + h2p) / 2.0
    elif h1p + h2p < 360.0:
        avg_hp = (h1p + h2p + 360.0) / 2.0
    else:
        avg_hp = (h1p + h2p - 360.0) / 2.0

    t = (
        1.0
        - 0.17 * cos(radians(avg_hp - 30.0))
        + 0.24 * cos(radians(2.0 * avg_hp))
        + 0.32 * cos(radians(3.0 * avg_hp + 6.0))
        - 0.20 * cos(radians(4.0 * avg_hp - 63.0))
    )
    delta_theta = 30.0 * exp(-(((avg_hp - 275.0) / 25.0) ** 2))
    r_c = 2.0 * sqrt(avg_cp ** 7 / (avg_cp ** 7 + 25.0 ** 7))
    s_l = 1.0 + (0.015 * (avg_lp - 50.0) ** 2) / sqrt(20.0 + (avg_lp - 50.0) ** 2)
    s_c = 1.0 + 0.045 * avg_cp
    s_h = 1.0 + 0.015 * avg_cp * t
    r_t = -sin(radians(2.0 * delta_theta)) * r_c

    lightness = delta_lp / (s_l * 1.0)
    chroma = delta_cp / (s_c * 1.0)
    hue = delta_h / (s_h * 1.0)
    return sqrt(
        lightness * lightness
        + chroma * chroma
        + hue * hue
        + r_t * chroma * hue
    )


def hue_degrees(y, x):
    if x == 0 and y == 0:
        return 0.0
    angle = degrees(atan2(y, x))
    return angle if angle >= 0.0 else angle + 360.0


def rgb_to_lab(rgb):
    red = linearize(rgb[0] / 255.0)
    green = linearize(rgb[1] / 255.0)
    blue = linearize(rgb[2] / 255.0)

    x = (red * 0.4124564 + green * 0.3575761 + blue * 0.1804375) / 0.95047
    y = red * 0.2126729 + green * 0.7151522 + blue * 0.0721750
    z = (red * 0.0193339 + green * 0.1191920 + blue * 0.9503041) / 1.08883

    return (
        116.0 * pivot(y) - 16.0,
        500.0 * (pivot(x) - pivot(y)),
        200.0 * (pivot(y) - pivot(z)),
    )


def linearize(channel):
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def pivot(value):
    delta = 6.0 / 29.0
    if value > delta ** 3:
        return cbrt(value)
    return value / (3.0 * delta * delta) + 4.0 / 29.0


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])
