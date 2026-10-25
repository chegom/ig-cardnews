"""Deterministic 4:5 Instagram card composition."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

from instacards.campaign import Campaign, Slide


CANVAS = (1080, 1350)
MARGIN_X = 92
SAFE_MARGIN_Y = 60
SAFE_AREA = (MARGIN_X, SAFE_MARGIN_Y, CANVAS[0] - MARGIN_X, CANVAS[1] - SAFE_MARGIN_Y)
FONT_ROOT = Path(__file__).resolve().parents[2] / "assets" / "fonts"
BOLD_FONT = FONT_ROOT / "Pretendard-Bold.otf"
REGULAR_FONT = FONT_ROOT / "Pretendard-Regular.otf"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.is_file():
        raise RuntimeError(f"font not found: {path}")
    return ImageFont.truetype(str(path), size=size)


def _fit_cover(image: Image.Image) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), CANVAS, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _gradient_overlay(size: tuple[int, int]) -> Image.Image:
    width, height = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = overlay.load()
    for y in range(height):
        vertical = 0.58 + 0.27 * (y / max(1, height - 1))
        for x in range(width):
            left = max(0.0, 1.0 - x / (width * 0.84))
            alpha = int(255 * min(0.82, vertical * (0.42 + 0.58 * left)))
            pixels[x, y] = (8, 10, 14, alpha)
    return overlay


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    result: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            result.append("")
            continue
        current = ""
        for token in paragraph.split(" ") if " " in paragraph else list(paragraph):
            separator = " " if " " in paragraph and current else ""
            candidate = f"{current}{separator}{token}"
            if current and _text_width(draw, candidate, font) > max_width:
                result.append(current)
                current = token
            else:
                current = candidate
        if current:
            result.append(current)
    return result


def _fit_title(draw: ImageDraw.ImageDraw, title: str, max_width: int, max_lines: int = 4) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(88, 51, -2):
        font = _font(BOLD_FONT, size)
        lines = _wrap(draw, title, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    raise ValueError(f"headline is too long for the card: {title}")


def _to_hex(color: object) -> str:
    if isinstance(color, str):
        return color.upper()
    red, green, blue = color[0], color[1], color[2]  # type: ignore[index]
    return f"#{red:02X}{green:02X}{blue:02X}"


def _union_bbox(boxes: list[tuple[int, int, int, int]]) -> list[int]:
    xs0 = [box[0] for box in boxes]
    ys0 = [box[1] for box in boxes]
    xs1 = [box[2] for box in boxes]
    ys1 = [box[3] for box in boxes]
    return [min(xs0), min(ys0), max(xs1), max(ys1)]


def _mean_rgb(image: Image.Image, bbox: list[int]) -> list[int]:
    left = max(0, min(bbox[0], image.width - 1))
    top = max(0, min(bbox[1], image.height - 1))
    right = max(left + 1, min(bbox[2], image.width))
    bottom = max(top + 1, min(bbox[3], image.height))
    region = image.crop((left, top, right, bottom))
    return [round(channel) for channel in ImageStat.Stat(region).mean[:3]]


def compose_slide(
    *,
    background: Path,
    slide: Slide,
    campaign: Campaign,
    index: int,
    output: Path,
    manifest: Path | None = None,
) -> None:
    with Image.open(background) as source:
        base = _fit_cover(source).convert("RGBA")
    base = Image.alpha_composite(base, _gradient_overlay(CANVAS))
    draw = ImageDraw.Draw(base)
    text_color = campaign.theme.text
    accent = campaign.theme.accent
    max_width = CANVAS[0] - MARGIN_X * 2

    eyebrow_font = _font(BOLD_FONT, 30)
    title_font, title_lines = _fit_title(draw, slide.headline, max_width)
    body_font = _font(REGULAR_FONT, 35)
    meta_font = _font(BOLD_FONT, 26)

    # Backgrounds are sampled before any glyphs land, so each element's
    # reported bg_rgb is the photo behind it, not the text we drew on top.
    bg_source = base.convert("RGB")
    elements: list[dict] = []

    def _record(role: str, boxes: list[tuple[int, int, int, int]], color: object, font_px: int, **extra: object) -> None:
        bbox = _union_bbox(boxes)
        elements.append(
            {
                "role": role,
                "bbox": bbox,
                "color": _to_hex(color),
                "bg_rgb": _mean_rgb(bg_source, bbox),
                "font_px": font_px,
                **extra,
            }
        )

    y = 105
    eyebrow = slide.eyebrow or f"{index:02d} / {len(campaign.slides):02d}"
    draw.rounded_rectangle((MARGIN_X, y, MARGIN_X + 52, y + 12), radius=6, fill=accent)
    draw.text((MARGIN_X + 68, y - 10), eyebrow, font=eyebrow_font, fill=accent)
    _record("eyebrow", [draw.textbbox((MARGIN_X + 68, y - 10), eyebrow, font=eyebrow_font)], accent, eyebrow_font.size, text=eyebrow)
    y += 95

    title_spacing = 15
    title_boxes: list[tuple[int, int, int, int]] = []
    for line in title_lines:
        draw.text((MARGIN_X, y), line, font=title_font, fill=text_color, stroke_width=1, stroke_fill=(0, 0, 0, 80))
        bbox = draw.textbbox((MARGIN_X, y), line, font=title_font)
        title_boxes.append(bbox)
        y = bbox[3] + title_spacing
    if title_boxes:
        _record("title", title_boxes, text_color, title_font.size, text=slide.headline.replace("\n", " "))

    if slide.body:
        y += 34
        body_lines = _wrap(draw, slide.body, body_font, max_width)
        if len(body_lines) > 5:
            raise ValueError(f"body is too long for slide {index}; limit it to about five lines")
        body_boxes: list[tuple[int, int, int, int]] = []
        for line in body_lines:
            draw.text((MARGIN_X, y), line, font=body_font, fill=(238, 240, 244, 255))
            bbox = draw.textbbox((MARGIN_X, y), line, font=body_font)
            body_boxes.append(bbox)
            y = bbox[3] + 16
        if body_boxes:
            _record("body", body_boxes, (238, 240, 244), body_font.size, text=slide.body, lines=len(body_lines))

    footer_y = CANVAS[1] - 105
    if campaign.theme.brand:
        draw.text((MARGIN_X, footer_y), campaign.theme.brand, font=meta_font, fill=(255, 255, 255, 205))
        _record("brand", [draw.textbbox((MARGIN_X, footer_y), campaign.theme.brand, font=meta_font)], (255, 255, 255), meta_font.size, text=campaign.theme.brand)
    page = f"{index}  —  {len(campaign.slides)}"
    page_width = _text_width(draw, page, meta_font)
    page_x = CANVAS[0] - MARGIN_X - page_width
    draw.text((page_x, footer_y), page, font=meta_font, fill=accent)
    _record("page", [draw.textbbox((page_x, footer_y), page, font=meta_font)], accent, meta_font.size, text=page)

    output.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(output, "JPEG", quality=94, optimize=True, progressive=True)

    if manifest is not None:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "slide": index,
            "canvas": list(CANVAS),
            "safe_area": list(SAFE_AREA),
            "card": str(output.resolve()),
            "elements": elements,
        }
        manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_draft_background(output: Path, index: int) -> None:
    width, height = CANVAS
    image = Image.new("RGB", CANVAS)
    pixels = image.load()
    phase = index * 0.73
    for y in range(height):
        for x in range(width):
            wave = (math.sin((x / width) * math.pi * 2 + phase) + 1) / 2
            r = int(23 + 34 * wave + 16 * y / height)
            g = int(28 + 23 * (1 - wave) + 10 * y / height)
            b = int(42 + 78 * wave + 25 * y / height)
            pixels[x, y] = (r, g, b)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "JPEG", quality=90)

