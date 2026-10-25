"""Full-bleed "AI tips" cover compositor.

Mirrors the reference carousel cover: an edge-to-edge photograph, a centred
letterspaced brand mark, a page pill, an outlined category capsule, and an
oversized Pretendard headline sitting on a deep bottom gradient.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from instacards import layout_record as rec
from instacards.editorial import BOLD_FONT, CANVAS


W, H = CANVAS
WHITE = (255, 255, 255)

BRAND_SIZE = 31
BRAND_TRACKING = 7
BRAND_TOP = 60

PAGE_SIZE = 30
PAGE_TOP = 48

BADGE_SIZE = 26
BADGE_TRACKING = 2
BADGE_HEIGHT = 56

MARGIN_X = 62

# Cover geometry measured off the reference carousel on a 1080x1350 canvas:
# badge pill 290x70 at x=50, headline ink rows 1050-1149 and 1168-1260.
# The reference face is narrower than Pretendard, so matching its glyph height
# would overfill the line -- the line's horizontal footprint (~80% of the
# canvas) is what reads as "size" in feed, so that is what we match.
COVER_MARGIN_X = 50
COVER_FIT_WIDTH = 880
COVER_MAX = 104
COVER_MIN = 70
COVER_PITCH_RATIO = 1.14         # tightened leading on two-line headlines
COVER_INK_BOTTOM = 150           # 표지 하단 여백 (살짝 띄움)
COVER_BADGE_HEIGHT = 70
COVER_BADGE_PAD_X = 30
COVER_BADGE_TO_TITLE = 53        # pill bottom -> first line ink top


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD_FONT), size=size)


def _width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _tracked_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, tracking: int) -> int:
    if not text:
        return 0
    return sum(_width(draw, char, font) for char in text) + tracking * (len(text) - 1)


def _draw_tracked(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    tracking: int,
    fill: tuple[int, int, int],
    shadow: bool = False,
) -> None:
    for char in text:
        if shadow:
            draw.text((x + 2, y + 2), char, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), char, font=font, fill=fill)
        x += _width(draw, char, font) + tracking


def _cap_height(font: ImageFont.FreeTypeFont) -> int:
    top, bottom = font.getbbox("가")[1], font.getbbox("가")[3]
    return bottom - top


def _photo(
    source: Image.Image,
    *,
    brightness: float = 1.0,
    saturation: float = 1.0,
    contrast: float = 1.0,
) -> Image.Image:
    """Fit the photograph to the canvas, with an optional grade.

    The cover is daylit while the interiors are shot at night; pulling the
    cover's exposure down closes the colour-temperature jump on swipe one
    without flattening the face that makes the cover stop a scroll.
    """
    canvas = ImageOps.fit(source.convert("RGB"), CANVAS, Image.Resampling.LANCZOS)
    canvas = ImageEnhance.Color(canvas).enhance(0.96 * saturation)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.04 * contrast)
    if brightness != 1.0:
        canvas = ImageEnhance.Brightness(canvas).enhance(brightness)
    return canvas.convert("RGBA")


def _gradient(
    canvas: Image.Image,
    *,
    start_y: int,
    full_y: int,
    max_alpha: int,
    tail_alpha: int | None = None,
    tint: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Smoothstep scrim from start_y to full_y, then an optional slow tail.

    The reference cover ramps hard over ~130px and then holds just short of
    opaque, so the photograph stays faintly readable behind the headline
    instead of dropping to flat black.
    """
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    span = max(1, full_y - start_y)
    tail_span = max(1, H - full_y)
    for y in range(start_y, H):
        if y <= full_y:
            t = (y - start_y) / span
            alpha = max_alpha * (t * t * (3 - 2 * t))
        elif tail_alpha is None:
            alpha = max_alpha
        else:
            alpha = max_alpha + (tail_alpha - max_alpha) * ((y - full_y) / tail_span)
        draw.line((0, y, W, y), fill=tint + (int(alpha),))
    canvas.alpha_composite(overlay)


TOP_SCRIM_ALPHA = 140   # 흰 하늘(≈250) 위에서도 흰 글자가 4.5:1을 넘기는 값
TOP_SCRIM_FLAT = 96     # 워드마크·페이지 필이 앉는 구간은 일정하게 유지
TOP_SCRIM_END = 240


def _top_scrim(
    canvas: Image.Image,
    *,
    max_alpha: int = TOP_SCRIM_ALPHA,
    flat_y: int = TOP_SCRIM_FLAT,
    end_y: int = TOP_SCRIM_END,
    tint: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Darken the top edge so the wordmark stays legible over a bright sky.

    The brand mark is white text with no plate of its own, so on a blown-out
    sky it measured 1.4:1 — invisible.  The band is flat where the furniture
    sits, then eases out so it reads as a vignette rather than a bar.
    """
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    span = max(1, end_y - flat_y)
    for y in range(end_y):
        if y <= flat_y:
            alpha = max_alpha
        else:
            t = (y - flat_y) / span
            alpha = max_alpha * (1 - t) ** 1.5
        draw.line((0, y, W, y), fill=tint + (int(alpha),))
    canvas.alpha_composite(overlay)


def _brand(draw: ImageDraw.ImageDraw, text: str, accent: tuple[int, int, int] | None = None) -> None:
    """Centred wordmark, optionally preceded by a small accent dot."""
    font = _font(BRAND_SIZE)
    width = _tracked_width(draw, text, font, BRAND_TRACKING)
    dot = 13
    lead = dot + 16 if accent else 0
    x = (W - (width + lead)) // 2
    if accent:
        cy = BRAND_TOP + _cap_height(font) // 2 + 3
        draw.ellipse((x, cy - dot // 2, x + dot, cy + dot // 2), fill=accent)
        x += lead
    _draw_tracked(
        draw,
        text,
        x=x,
        y=BRAND_TOP,
        font=font,
        tracking=BRAND_TRACKING,
        fill=(255, 255, 255),
        shadow=True,
    )


def _page_pill(draw: ImageDraw.ImageDraw, index: int, total: int) -> None:
    font = _font(PAGE_SIZE)
    label = f"{index}/{total}"
    width = _width(draw, label, font) + 46
    height = 58
    x = W - 58 - width
    draw.rounded_rectangle((x, PAGE_TOP, x + width, PAGE_TOP + height), radius=height // 2, fill=(14, 16, 20, 168))
    draw.text((x + width // 2, PAGE_TOP + height // 2), label, font=font, fill=WHITE, anchor="mm")


def _badge(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    x: int,
    y: int,
    height: int = BADGE_HEIGHT,
    pad_x: int = 26,
    fill: tuple[int, int, int, int] | None = (10, 12, 16, 92),
) -> int:
    font = _font(BADGE_SIZE)
    width = _tracked_width(draw, text, font, BADGE_TRACKING) + pad_x * 2
    draw.rounded_rectangle(
        (x, y, x + width, y + height), radius=height // 2, fill=fill, outline=WHITE, width=2
    )
    box = draw.textbbox((0, 0), text, font=font)
    _draw_tracked(
        draw,
        text,
        x=x + pad_x,
        y=y + (height - (box[3] - box[1])) // 2 - box[1],
        font=font,
        tracking=BADGE_TRACKING,
        fill=WHITE,
    )
    return width


def _record_brand(draw: ImageDraw.ImageDraw, brand: str) -> None:
    font = _font(BRAND_SIZE)
    width = _tracked_width(draw, brand, font, BRAND_TRACKING)
    x = (W - width) // 2
    rec.record("brand", (x, BRAND_TOP, x + width, BRAND_TOP + _cap_height(font)), WHITE, BRAND_SIZE, text=brand)


def _record_page(draw: ImageDraw.ImageDraw, index: int, total: int) -> None:
    font = _font(PAGE_SIZE)
    label = f"{index}/{total}"
    width = _width(draw, label, font) + 46
    x = W - 58 - width
    rec.record("page", (x, PAGE_TOP, x + width, PAGE_TOP + 58), WHITE, PAGE_SIZE, bg_rgb=(14, 16, 20), text=label)


def _fit_headline(draw: ImageDraw.ImageDraw, lines: list[str], width: int) -> ImageFont.FreeTypeFont:
    for size in range(COVER_MAX, COVER_MIN - 1, -2):
        font = _font(size)
        if all(_width(draw, line, font) <= width for line in lines):
            return font
    raise ValueError(f"headline does not fit at minimum size: {lines}")


def compose_cover(
    *,
    source: Path,
    spec: dict[str, Any],
    index: int,
    total: int,
    output: Path,
) -> None:
    title = spec.get("title")
    if not title:
        raise ValueError("cover requires a title")
    lines = [line for line in title.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 3:
        raise ValueError("cover headline must be 1-3 lines")

    with Image.open(source) as opened:
        canvas = _photo(
            opened.copy(),
            brightness=spec.get("grade_brightness", 1.0),
            saturation=spec.get("grade_saturation", 1.0),
            contrast=spec.get("grade_contrast", 1.0),
        )

    _gradient(
        canvas,
        start_y=spec.get("gradient_start", 830),
        full_y=spec.get("gradient_full", 965),
        max_alpha=spec.get("gradient_alpha", 206),
        tail_alpha=spec.get("gradient_tail", 248),
    )
    # Every scrim must be down before the snapshot, or the audit measures a
    # backdrop the viewer never sees.
    if spec.get("brand"):
        _top_scrim(canvas)
    rec.set_background(canvas)
    draw = ImageDraw.Draw(canvas)

    if spec.get("brand"):
        _brand(draw, spec["brand"])
        _record_brand(draw, spec["brand"])
    _page_pill(draw, index, total)
    _record_page(draw, index, total)

    font = _fit_headline(draw, lines, COVER_FIT_WIDTH)
    inks = [draw.textbbox((0, 0), line, font=font) for line in lines]
    pitch = round(max(box[3] - box[1] for box in inks) * COVER_PITCH_RATIO)

    # Anchor on the last line's ink bottom, then stack upward by a fixed pitch.
    last_origin = H - COVER_INK_BOTTOM - inks[-1][3]
    origins = [last_origin - (len(lines) - 1 - i) * pitch for i in range(len(lines))]

    if spec.get("badge"):
        badge_y = origins[0] + inks[0][1] - COVER_BADGE_TO_TITLE - COVER_BADGE_HEIGHT
        badge_w = _badge(
            draw,
            spec["badge"],
            x=COVER_MARGIN_X,
            y=badge_y,
            height=COVER_BADGE_HEIGHT,
            pad_x=COVER_BADGE_PAD_X,
            fill=None,
        )
        rec.record("kicker", (COVER_MARGIN_X, badge_y, COVER_MARGIN_X + badge_w, badge_y + COVER_BADGE_HEIGHT),
                   WHITE, BADGE_SIZE, text=spec["badge"])

    title_right = COVER_MARGIN_X + max((_width(draw, line, font) for line in lines), default=0)
    for line, origin in zip(lines, origins):
        draw.text((COVER_MARGIN_X, origin), line, font=font, fill=WHITE)
    rec.record("title", (COVER_MARGIN_X, origins[0] + inks[0][1], title_right, origins[-1] + inks[-1][3]),
               WHITE, font.size, text=" ".join(lines))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(
        output, "JPEG", quality=96, subsampling=0, optimize=True, progressive=True
    )


def compose_cover_set(spec_path: Path, background: Path, output: Path) -> list[Path]:
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    total = payload.get("total", 8)
    shared = {k: v for k, v in payload.items() if k not in ("candidates", "total")}
    written: list[Path] = []
    for position, candidate in enumerate(payload["candidates"], start=1):
        spec = {**shared, **candidate}
        target = output / f"{position:02d}.jpg"
        compose_cover(source=background, spec=spec, index=1, total=total, output=target)
        written.append(target)
    return written
