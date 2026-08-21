from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BOARD_SIZE = 29


def export_pattern(pattern, file_format):
    image = render_pattern_image(pattern)
    buffer = BytesIO()

    if file_format == "pdf":
        image.convert("RGB").save(buffer, format="PDF", resolution=150.0)
        mime_type = "application/pdf"
        extension = "pdf"
    else:
        image.save(buffer, format="PNG")
        mime_type = "image/png"
        extension = "png"

    buffer.seek(0)
    return buffer, mime_type, f"bead-pattern-{pattern['id']}.{extension}"


def render_pattern_image(pattern):
    width = pattern["width"]
    height = pattern["height"]
    cell_size = 18 if max(width, height) <= 60 else 12
    margin = 48
    header_height = 136
    legend_item_height = 42
    legend_columns = 2
    legend_rows = (len(pattern["palette"]) + legend_columns - 1) // legend_columns
    legend_height = 88 + legend_rows * legend_item_height
    chart_width = width * cell_size
    chart_height = height * cell_size
    image_width = max(960, chart_width + margin * 2)
    image_height = margin + header_height + chart_height + legend_height + margin

    image = Image.new("RGB", (image_width, image_height), "#fffaf4")
    draw = ImageDraw.Draw(image)
    title_font = load_font(34)
    text_font = load_font(22)
    small_font = load_font(16)
    symbol_font = load_font(11)
    palette_map = {color["id"]: color for color in pattern["palette"]}

    draw.rounded_rectangle((24, 24, image_width - 24, image_height - 24), radius=28, fill="#ffffff", outline="#efdcc8", width=2)
    draw_text(draw, (margin, 46), "拼豆图纸", fill="#2f2a24", font=title_font)
    summary = f"尺寸 {width}×{height}｜总豆数 {pattern['totalBeads']}｜颜色 {len(pattern['palette'])}｜底板 {pattern['board']['count']} 块"
    draw_text(draw, (margin, 92), summary, fill="#7b6856", font=text_font)

    chart_left = (image_width - chart_width) // 2
    chart_top = margin + header_height

    for row_index, row in enumerate(pattern["grid"]):
        for column_index, color_id in enumerate(row):
            color = palette_map[color_id]
            left = chart_left + column_index * cell_size
            top = chart_top + row_index * cell_size
            right = left + cell_size
            bottom = top + cell_size
            draw.rectangle((left, top, right, bottom), fill=color["hex"], outline="#cdb8a3")

            if cell_size >= 16:
                symbol = color["symbol"]
                bbox = draw.textbbox((0, 0), symbol, font=symbol_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                draw_text(
                    draw,
                    (left + (cell_size - text_width) / 2, top + (cell_size - text_height) / 2 - 1),
                    symbol,
                    fill=text_color(color["rgb"]),
                    font=symbol_font
                )

    draw_board_lines(draw, chart_left, chart_top, width, height, cell_size)

    legend_top = chart_top + chart_height + 44
    draw_text(draw, (margin, legend_top), "色块清单", fill="#2f2a24", font=title_font)
    item_width = (image_width - margin * 2) // legend_columns

    for index, color in enumerate(pattern["palette"]):
        column = index % legend_columns
        row = index // legend_columns
        x = margin + column * item_width
        y = legend_top + 54 + row * legend_item_height
        draw.rounded_rectangle((x, y, x + 28, y + 28), radius=6, fill=color["hex"], outline="#b9aa9a", width=1)
        label = f"{color['symbol']} {color['name']} {color['id']}：{color['count']}颗，备{color['suggestCount']}颗"
        draw_text(draw, (x + 40, y + 3), label, fill="#4a3b2d", font=small_font)

    return image


def draw_board_lines(draw, left, top, width, height, cell_size):
    right = left + width * cell_size
    bottom = top + height * cell_size
    for column in range(0, width + 1, BOARD_SIZE):
        x = left + column * cell_size
        draw.line((x, top, x, bottom), fill="#5b4533", width=2)
    for row in range(0, height + 1, BOARD_SIZE):
        y = top + row * cell_size
        draw.line((left, y, right, y), fill="#5b4533", width=2)
    draw.rectangle((left, top, right, bottom), outline="#2f2a24", width=2)


def load_font(size):
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for font_path in font_paths:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)

    return ImageFont.load_default()


def draw_text(draw, position, text, fill, font):
    try:
        draw.text(position, text, fill=fill, font=font)
    except UnicodeEncodeError:
        fallback = text.encode("ascii", "ignore").decode("ascii")
        draw.text(position, fallback, fill=fill, font=font)


def text_color(rgb):
    brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000
    return "#2f2a24" if brightness > 150 else "#ffffff"
