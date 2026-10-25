"""Photo-first compositor for editorial Instagram carousel probes.

Every card is treated as a standalone cover: a full-bleed photograph, a
compact capsule label, and a large Pretendard headline over a dark gradient.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from instacards import layout_record as rec
from instacards.editorial import BOLD_FONT, CANVAS, REGULAR_FONT


W, H = CANVAS
PROBE_WHITE = (255, 255, 255)
PROBE_PINK = (255, 55, 132)
SAFE_AREA = (50, 40, W - 50, H - 40)


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    top, bottom = font.getbbox("가")[1], font.getbbox("가")[3]
    return bottom - top


def _photo(source: Image.Image) -> Image.Image:
    canvas = ImageOps.fit(source.convert("RGB"), CANVAS, Image.Resampling.LANCZOS)
    canvas = ImageEnhance.Color(canvas).enhance(0.94)
    return ImageEnhance.Contrast(canvas).enhance(1.03).convert("RGBA")


def _bottom_gradient(canvas: Image.Image, *, start_y: int, max_alpha: int) -> None:
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    span = H - start_y
    for y in range(start_y, H):
        progress = (y - start_y) / max(1, span - 1)
        alpha = int(max_alpha * (progress**1.35))
        draw.line((0, y, W, y), fill=(0, 0, 0, alpha))
    canvas.alpha_composite(overlay)


def _capsule(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    x: int,
    y: int,
    centered: bool = False,
) -> tuple[int, int, int, int]:
    font = _font(BOLD_FONT, 30)
    pad_x, pad_y = 24, 13
    width = _width(draw, text, font) + pad_x * 2
    height = 58
    if centered:
        x = (W - width) // 2
    box = (x, y, x + width, y + height)
    draw.rounded_rectangle(box, radius=height // 2, fill=(12, 14, 18, 116), outline=PROBE_WHITE, width=2)
    draw.text((x + pad_x, y + pad_y - 3), text, font=font, fill=PROBE_WHITE)
    return box


def _page_marker(draw: ImageDraw.ImageDraw, page: str) -> None:
    font = _font(BOLD_FONT, 26)
    width, height = 124, 54
    x, y = W - 68 - width, 54
    draw.rounded_rectangle((x, y, x + width, y + height), radius=27, fill=(13, 15, 19, 174))
    text_x = x + (width - _width(draw, page, font)) // 2
    draw.text((text_x, y + 10), page, font=font, fill=PROBE_WHITE)
    # The page marker sits on its own dark pill, not on the photo.
    rec.record("page", (x, y, x + width, y + height), PROBE_WHITE, 26, bg_rgb=(13, 15, 19), text=page)


def _record_title(draw: ImageDraw.ImageDraw, lines: list[str], *, x: int, y: int, bottom: int, font, centered: bool) -> None:
    maxw = max((_width(draw, line, font) for line in lines), default=0)
    left = (W - maxw) // 2 if centered else x
    rec.record("title", (left, y, left + maxw, bottom), PROBE_WHITE, font.size, text=" ".join(lines))


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    gap: int,
    centered: bool = False,
    accent_last: bool = False,
) -> int:
    line_height = _line_height(font)
    for index, line in enumerate(lines):
        line_x = (W - _width(draw, line, font)) // 2 if centered else x
        color = PROBE_PINK if accent_last and index == len(lines) - 1 else fill
        draw.text((line_x, y), line, font=font, fill=color, stroke_width=1, stroke_fill=(0, 0, 0))
        y += line_height + gap
    return y


def _bottom_story(source: Image.Image, spec: dict[str, Any], page: str) -> Image.Image:
    canvas = _photo(source)
    _bottom_gradient(canvas, start_y=585, max_alpha=238)
    rec.set_background(canvas)
    draw = ImageDraw.Draw(canvas)
    _page_marker(draw, page)

    lines = spec["title"].splitlines()
    title_font = _font(BOLD_FONT, 102 if len(lines) <= 2 else 88)
    line_height = _line_height(title_font)
    title_height = len(lines) * line_height + max(0, len(lines) - 1) * 14
    body = spec.get("body", "")
    body_height = 52 if body else 0
    title_y = H - 94 - body_height - title_height
    pill_y = title_y - 86
    _capsule(draw, spec.get("kicker", "생활 가이드"), x=68, y=pill_y)
    title_bottom = _draw_lines(
        draw,
        lines,
        x=64,
        y=title_y,
        font=title_font,
        fill=PROBE_WHITE,
        gap=14,
    )
    _record_title(draw, lines, x=64, y=title_y, bottom=title_bottom, font=title_font, centered=False)
    if body:
        body_font = _font(REGULAR_FONT, 34)
        draw.text((68, title_bottom + 10), body, font=body_font, fill=(240, 241, 244))
        rec.record("body", (68, title_bottom + 10, 68 + _width(draw, body, body_font), title_bottom + 10 + _line_height(body_font)),
                   (240, 241, 244), body_font.size, lines=1, text=body)
    return canvas


def _center_alert(source: Image.Image, spec: dict[str, Any], page: str) -> Image.Image:
    canvas = _photo(source)
    _bottom_gradient(canvas, start_y=430, max_alpha=248)
    rec.set_background(canvas)
    draw = ImageDraw.Draw(canvas)
    _page_marker(draw, page)

    lines = spec["title"].splitlines()
    title_font = _font(BOLD_FONT, 94)
    line_height = _line_height(title_font)
    title_height = len(lines) * line_height + max(0, len(lines) - 1) * 10
    title_y = 760 - title_height // 2
    _capsule(draw, spec.get("kicker", "긴급 행동"), x=0, y=title_y - 88, centered=True)
    title_bottom = _draw_lines(
        draw,
        lines,
        x=0,
        y=title_y,
        font=title_font,
        fill=PROBE_WHITE,
        gap=10,
        centered=True,
        accent_last=True,
    )
    _record_title(draw, lines, x=0, y=title_y, bottom=title_bottom, font=title_font, centered=True)
    body = spec.get("body", "")
    if body:
        body_font = _font(BOLD_FONT, 34)
        body_x = (W - _width(draw, body, body_font)) // 2
        draw.text((body_x, title_bottom + 36), body, font=body_font, fill=(240, 241, 244))
        rec.record("body", (body_x, title_bottom + 36, body_x + _width(draw, body, body_font), title_bottom + 36 + _line_height(body_font)),
                   (240, 241, 244), body_font.size, lines=1, text=body)
    draw.text((W // 2, 1236), "옆으로 넘겨 행동 순서를 확인하세요", font=_font(REGULAR_FONT, 27), fill=(225, 227, 232), anchor="mm")
    return canvas


LAYOUT_RENDERERS = {
    "bottom_story": _bottom_story,
    "center_alert": _center_alert,
}

ROLE_DEFAULT_LAYOUT = {
    "cover": "bottom_story",
    "general_info": "bottom_story",
    "emergency_alert": "center_alert",
}


def _number_for_slide(slide_id: str) -> int:
    match = re.fullmatch(r"s(\d{2})", slide_id)
    if not match:
        raise ValueError(f"invalid slide_id: {slide_id}")
    return int(match.group(1))


def compose_probe_slide(
    *,
    spec: dict[str, Any],
    backgrounds: Path,
    output: Path,
    total: int = 8,
) -> None:
    role = spec.get("role")
    if role not in ROLE_DEFAULT_LAYOUT:
        raise ValueError(f"unknown probe role: {role}")
    if not spec.get("title"):
        raise ValueError("probe slide requires a title")

    layout = spec.get("layout", ROLE_DEFAULT_LAYOUT[role])
    if layout not in LAYOUT_RENDERERS:
        raise ValueError(f"unknown probe layout: {layout}")

    number = _number_for_slide(spec["slide_id"])
    page = f"{number:02d} / {total:02d}"
    source_path = backgrounds / f"{number:02d}.jpg"
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    rec.start()
    try:
        with Image.open(source_path) as opened:
            image = LAYOUT_RENDERERS[layout](opened.copy(), spec, page)
        elements = rec.finish()
    finally:
        if rec.active():
            rec.finish()

    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(
        output,
        "JPEG",
        quality=96,
        subsampling=0,
        optimize=True,
        progressive=True,
    )
    manifest = output.with_suffix(".layout.json")
    manifest.write_text(
        json.dumps(
            {"slide": number, "canvas": list(CANVAS), "safe_area": list(SAFE_AREA), "card": str(output.resolve()), "elements": elements},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def compose_probe_carousel(spec_path: Path, backgrounds: Path, output: Path) -> None:
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    slides = payload["slides"]
    if not 1 <= len(slides) <= 10:
        raise ValueError("Instagram carousel must have 1-10 slides")
    for spec in slides:
        number = _number_for_slide(spec["slide_id"])
        compose_probe_slide(
            spec=spec,
            backgrounds=backgrounds,
            output=output / f"{number:02d}.jpg",
        )
