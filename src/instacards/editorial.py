"""High-quality editorial card composition for educational carousels.

The image model supplies text-free photography.  This module owns every glyph,
shape, crop, and safety margin so Korean copy remains exact and legible.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from instacards import layout_record as rec


CANVAS = (1080, 1350)
W, H = CANVAS
SAFE_AREA = (50, 40, W - 50, H - 40)
FONT_ROOT = Path(__file__).resolve().parents[2] / "assets" / "fonts"
BOLD_FONT = FONT_ROOT / "Pretendard-Bold.otf"
REGULAR_FONT = FONT_ROOT / "Pretendard-Regular.otf"

PAPER = "#F4F0E8"
INK = "#111A2E"
BLUE = "#2864D7"
ICE = "#CBEAFF"
ORANGE = "#FF6848"
WHITE = "#FFFFFF"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        tokens = paragraph.split(" ") if " " in paragraph else list(paragraph)
        line = ""
        for token in tokens:
            joiner = " " if " " in paragraph and line else ""
            trial = f"{line}{joiner}{token}"
            if line and _text_width(draw, trial, font) > width:
                lines.append(line)
                line = token
            else:
                line = trial
        if line:
            lines.append(line)
    return lines


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    width: int,
    max_lines: int,
    start: int,
    minimum: int,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(start, minimum - 1, -2):
        font = _font(BOLD_FONT, size)
        lines = _wrap(draw, text, font, width)
        if len(lines) <= max_lines:
            return font, lines
    raise ValueError(f"text does not fit: {text}")


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    fill: str,
    gap: int,
) -> int:
    x, y = xy
    start_y = y
    right = x
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line or "가", font=font)
        right = max(right, bbox[2])
        y = bbox[3] + gap
    # Every substantive copy block (title, body, bullet, checklist row) flows
    # through here, so this is where the audit records editorial text.  The card
    # behind it is snapshotted by each layout before the first block is drawn.
    filled = sum(1 for line in lines if line.strip())
    if filled:
        rec.record("text", (x, start_y, right, max(start_y + 1, y - gap)), fill, font.size, lines=filled)
    return y


def _rounded_photo(source: Image.Image, box: tuple[int, int, int, int], radius: int = 36) -> Image.Image:
    x1, y1, x2, y2 = box
    size = (x2 - x1, y2 - y1)
    image = ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)
    image = ImageEnhance.Color(image).enhance(0.88)
    image = ImageEnhance.Contrast(image).enhance(1.04)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *size), radius=radius, fill=255)
    layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    layer.paste(image.convert("RGBA"), (x1, y1), mask)
    return layer


def _paper_texture(image: Image.Image, seed: int) -> Image.Image:
    rng = random.Random(seed)
    noise = Image.new("RGBA", CANVAS, (255, 255, 255, 0))
    draw = ImageDraw.Draw(noise)
    for _ in range(5200):
        x = rng.randrange(W)
        y = rng.randrange(H)
        alpha = rng.randrange(2, 10)
        tone = rng.choice((20, 240))
        draw.point((x, y), fill=(tone, tone, tone, alpha))
    return Image.alpha_composite(image.convert("RGBA"), noise.filter(ImageFilter.GaussianBlur(0.35)))


def _header(draw: ImageDraw.ImageDraw, index: int, total: int, *, dark: bool = False) -> None:
    color = WHITE if dark else INK
    tiny = _font(BOLD_FONT, 25)
    draw.text((72, 52), "WINTER READY", font=tiny, fill=color)
    page = f"{index:02d} / {total:02d}"
    draw.text((W - 72 - _text_width(draw, page, tiny), 52), page, font=tiny, fill=color)


def _footer(draw: ImageDraw.ImageDraw, *, dark: bool = False) -> None:
    color = ICE if dark else BLUE
    tiny = _font(BOLD_FONT, 21)
    draw.text((72, H - 62), "SAVE · CHECK · SHARE", font=tiny, fill=color)


def _snowflake(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, color: str) -> None:
    """Draw a font-independent six-spoke snowflake."""
    cx, cy = center
    for degrees in (0, 60, 120):
        angle = math.radians(degrees)
        dx = math.cos(angle) * radius
        dy = math.sin(angle) * radius
        draw.line((cx - dx, cy - dy, cx + dx, cy + dy), fill=color, width=7)
        for direction in (-1, 1):
            end_x = cx + direction * dx
            end_y = cy + direction * dy
            for branch_degrees in (-35, 35):
                branch_angle = angle + (math.pi if direction < 0 else 0) + math.radians(branch_degrees)
                branch = radius * 0.32
                draw.line(
                    (
                        end_x,
                        end_y,
                        end_x - math.cos(branch_angle) * branch,
                        end_y - math.sin(branch_angle) * branch,
                    ),
                    fill=color,
                    width=5,
                )


def _kicker(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, color: str = BLUE) -> int:
    font = _font(BOLD_FONT, 25)
    width = _text_width(draw, text, font)
    draw.rounded_rectangle((x, y, x + width + 32, y + 46), radius=23, fill=color)
    draw.text((x + 16, y + 8), text, font=font, fill=WHITE)
    return y + 66


def _body(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], *, color: str = INK) -> int:
    x1, y1, x2, _ = box
    font = _font(REGULAR_FONT, 38)
    lines = _wrap(draw, text, font, x2 - x1)
    return _draw_lines(draw, (x1, y1), lines, font, color, 14)


def _bullets(
    draw: ImageDraw.ImageDraw,
    items: list[str],
    box: tuple[int, int, int, int],
    *,
    accent: str = BLUE,
    color: str = INK,
    numbered: bool = False,
) -> None:
    x1, y, x2, y2 = box
    font = _font(BOLD_FONT, 35)
    num_font = _font(BOLD_FONT, 24)
    for idx, item in enumerate(items, start=1):
        lines = _wrap(draw, item, font, x2 - x1 - 62)
        line_height = 45
        item_height = max(62, len(lines) * line_height + 17)
        if y + item_height > y2:
            raise ValueError("bullet copy exceeds its layout box")
        if numbered:
            draw.ellipse((x1, y + 2, x1 + 42, y + 44), fill=accent)
            label = str(idx)
            label_w = _text_width(draw, label, num_font)
            draw.text((x1 + (42 - label_w) / 2, y + 8), label, font=num_font, fill=WHITE)
        else:
            draw.rounded_rectangle((x1 + 5, y + 14, x1 + 27, y + 36), radius=7, fill=accent)
        _draw_lines(draw, (x1 + 58, y), lines, font, color, 7)
        y += item_height + 17


def _cover(source: Image.Image, spec: dict[str, Any], index: int, total: int) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, PAPER)
    photo = ImageOps.fit(source.convert("RGB"), (W, 600), Image.Resampling.LANCZOS)
    canvas.paste(photo, (0, 0))
    veil = Image.new("RGBA", (W, 600), (15, 27, 48, 55))
    canvas.alpha_composite(veil, (0, 0))
    draw = ImageDraw.Draw(canvas)
    _header(draw, index, total, dark=True)
    draw.rounded_rectangle((66, 548, W - 66, H - 68), radius=44, fill=PAPER)
    rec.set_background(canvas)
    y = _kicker(draw, spec.get("kicker", "겨울 생활 가이드"), 112, 612, ORANGE)
    font, lines = _fit_text(draw, spec["title"], 832, 3, 94, 64)
    y = _draw_lines(draw, (112, y + 18), lines, font, INK, 10)
    if spec.get("body"):
        body_font = _font(REGULAR_FONT, 40)
        body_lines = _wrap(draw, spec["body"], body_font, 792)
        _draw_lines(draw, (112, y + 30), body_lines, body_font, INK, 13)
    draw.rounded_rectangle((850, 112, 1006, 268), radius=78, fill=ORANGE)
    _snowflake(draw, (928, 190), 40, WHITE)
    _footer(draw)
    return _paper_texture(canvas, index)


def _split(source: Image.Image, spec: dict[str, Any], index: int, total: int) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, INK)
    canvas = Image.alpha_composite(canvas, _rounded_photo(source, (554, 112, 1012, 1238), 40))
    draw = ImageDraw.Draw(canvas)
    rec.set_background(canvas)
    _header(draw, index, total, dark=True)
    y = _kicker(draw, spec.get("kicker", "핵심"), 72, 145, ORANGE)
    font, lines = _fit_text(draw, spec["title"], 420, 5, 72, 52)
    y = _draw_lines(draw, (72, y + 24), lines, font, WHITE, 12)
    if spec.get("body"):
        y = _body(draw, spec["body"], (72, y + 30, 492, 850), color=ICE)
    if spec.get("bullets"):
        _bullets(draw, spec["bullets"], (72, y + 38, 510, 1192), accent=ORANGE, color=WHITE)
    _footer(draw, dark=True)
    return _paper_texture(canvas, index)


def _photo_memo(source: Image.Image, spec: dict[str, Any], index: int, total: int) -> Image.Image:
    canvas = ImageOps.fit(source.convert("RGB"), CANVAS, Image.Resampling.LANCZOS).convert("RGBA")
    tint = Image.new("RGBA", CANVAS, (18, 39, 77, 48))
    canvas = Image.alpha_composite(canvas, tint)
    draw = ImageDraw.Draw(canvas)
    _header(draw, index, total, dark=True)
    draw.rounded_rectangle((64, 210, 798, 1194), radius=42, fill=(244, 240, 232, 244))
    draw.rectangle((98, 210, 160, 224), fill=ORANGE)
    rec.set_background(canvas)
    y = _kicker(draw, spec.get("kicker", "집 안"), 112, 266, BLUE)
    font, lines = _fit_text(draw, spec["title"], 620, 4, 76, 54)
    y = _draw_lines(draw, (112, y + 22), lines, font, INK, 10)
    if spec.get("body"):
        y = _body(draw, spec["body"], (112, y + 28, 720, 800))
    if spec.get("bullets"):
        _bullets(draw, spec["bullets"], (112, y + 32, 720, 1128), accent=ORANGE)
    _footer(draw, dark=True)
    return _paper_texture(canvas, index)


def _steps(source: Image.Image, spec: dict[str, Any], index: int, total: int) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, PAPER)
    canvas = Image.alpha_composite(canvas, _rounded_photo(source, (72, 430, 1008, 800), 38))
    draw = ImageDraw.Draw(canvas)
    rec.set_background(canvas)
    _header(draw, index, total)
    y = _kicker(draw, spec.get("kicker", "미리 막기"), 72, 130, BLUE)
    font, lines = _fit_text(draw, spec["title"], 900, 2, 78, 58)
    _draw_lines(draw, (72, y + 16), lines, font, INK, 8)
    if spec.get("bullets"):
        _bullets(draw, spec["bullets"], (72, 850, 1008, 1246), accent=ORANGE, numbered=True)
    _footer(draw)
    return _paper_texture(canvas, index)


def _alert(source: Image.Image, spec: dict[str, Any], index: int, total: int) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, ORANGE)
    canvas = Image.alpha_composite(canvas, _rounded_photo(source, (72, 112, 1008, 548), 42))
    draw = ImageDraw.Draw(canvas)
    _header(draw, index, total, dark=True)
    draw.rounded_rectangle((72, 506, 1008, 1240), radius=42, fill=INK)
    rec.set_background(canvas)
    y = _kicker(draw, spec.get("kicker", "위험 신호"), 112, 558, ORANGE)
    font, lines = _fit_text(draw, spec["title"], 840, 3, 76, 54)
    y = _draw_lines(draw, (112, y + 16), lines, font, WHITE, 9)
    if spec.get("body"):
        y = _body(draw, spec["body"], (112, y + 22, 948, 950), color=ICE)
    if spec.get("bullets"):
        _bullets(draw, spec["bullets"], (112, y + 26, 948, 1172), accent=ORANGE, color=WHITE)
    _footer(draw, dark=True)
    return _paper_texture(canvas, index)


def _checklist(source: Image.Image, spec: dict[str, Any], index: int, total: int) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, ICE)
    canvas = Image.alpha_composite(canvas, _rounded_photo(source, (636, 100, 1012, 460), 188))
    draw = ImageDraw.Draw(canvas)
    rec.set_background(canvas)
    _header(draw, index, total)
    y = _kicker(draw, spec.get("kicker", "오늘 바로"), 72, 145, ORANGE)
    font, lines = _fit_text(draw, spec["title"], 520, 4, 78, 56)
    y = _draw_lines(draw, (72, y + 14), lines, font, INK, 8)
    items = spec.get("bullets", [])
    list_top = max(490, y + 35)
    draw.rounded_rectangle((72, list_top, 1008, 1194), radius=40, fill=PAPER)
    rec.set_background(canvas)  # items sit on the inner paper card, not the ICE base
    bullet_font = _font(BOLD_FONT, 35)
    row_y = list_top + 56
    for item in items:
        draw.rounded_rectangle((120, row_y + 2, 164, row_y + 46), radius=11, outline=BLUE, width=4)
        lines = _wrap(draw, item, bullet_font, 750)
        row_y = _draw_lines(draw, (194, row_y), lines, bullet_font, INK, 8) + 30
        draw.line((120, row_y - 13, 952, row_y - 13), fill="#D5D2CB", width=2)
    _footer(draw)
    return _paper_texture(canvas, index)


LAYOUTS = {
    "cover": _cover,
    "split": _split,
    "photo_memo": _photo_memo,
    "steps": _steps,
    "alert": _alert,
    "checklist": _checklist,
}


def compose_editorial_slide(
    *, source: Path, spec: dict[str, Any], index: int, total: int, output: Path
) -> None:
    layout = spec.get("layout", "split")
    if layout not in LAYOUTS:
        raise ValueError(f"unknown editorial layout: {layout}")
    rec.start()
    try:
        with Image.open(source) as opened:
            image = LAYOUTS[layout](opened.copy(), spec, index, total)
        elements = rec.finish()
    finally:
        if rec.active():
            rec.finish()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, "JPEG", quality=95, optimize=True, progressive=True)
    output.with_suffix(".layout.json").write_text(
        json.dumps(
            {"slide": index, "canvas": list(CANVAS), "safe_area": list(SAFE_AREA), "card": str(output.resolve()), "elements": elements},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def compose_editorial_carousel(spec_path: Path, backgrounds: Path, output: Path) -> None:
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    slides = payload["slides"]
    if not 1 <= len(slides) <= 10:
        raise ValueError("Instagram carousel must have 1-10 slides")
    for index, spec in enumerate(slides, start=1):
        source = backgrounds / f"{index:02d}.jpg"
        if not source.is_file():
            raise FileNotFoundError(source)
        compose_editorial_slide(
            source=source,
            spec=spec,
            index=index,
            total=len(slides),
            output=output / f"{index:02d}.jpg",
        )
