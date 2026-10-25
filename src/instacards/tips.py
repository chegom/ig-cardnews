"""Interior slides for the full-bleed "AI tips" carousel.

Slide one is the photographic cover owned by :mod:`instacards.cover`.  The
remaining slides alternate between the same full-bleed photo treatment and
near-black editorial cards so dense Korean copy — a prompt block, numbered
points — stays legible at feed size while the brand furniture stays identical.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from instacards import layout_record as rec
from instacards.cover import (
    MARGIN_X,
    _top_scrim,
    _badge,
    _draw_tracked,
    _brand,
    _cap_height,
    _font,
    _gradient,
    _page_pill,
    _photo,
    _record_brand,
    _record_page,
    _width,
    compose_cover,
)
from instacards.editorial import CANVAS, REGULAR_FONT

W, H = CANVAS
WHITE = (255, 255, 255)
PAPER_DIM = (214, 217, 224)
INK = (11, 13, 17)
ACCENT = (255, 104, 72)          # 기본값; copy JSON의 "accent"로 덮어쓴다
PANEL = (23, 26, 32)
HAIRLINE = (58, 63, 73)


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _accent(spec: dict[str, Any]) -> tuple[int, int, int]:
    raw = spec.get("accent")
    return _hex(raw) if isinstance(raw, str) else ACCENT


def _kicker_height() -> int:
    font = _font(KICKER_SIZE)
    box = font.getbbox("가")
    return (box[3] - box[1]) + KICKER_GAP


def _kicker(draw: ImageDraw.ImageDraw, text: str, *, x: int, y: int, fill: tuple[int, int, int] = ACCENT) -> int:
    """Interior pages use a plain letterspaced kicker; the pill badge is a
    cover device and loses its weight when it appears on every slide."""
    font = _font(KICKER_SIZE)
    box = font.getbbox("가")
    _draw_tracked(draw, text, x=x, y=y - box[1], font=font, tracking=KICKER_TRACKING, fill=fill)
    return y + (box[3] - box[1]) + KICKER_GAP


def _regular(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(REGULAR_FONT), size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for token in paragraph.split(" "):
            trial = f"{line} {token}".strip()
            if line and _width(draw, trial, font) > width:
                lines.append(line)
                line = token
            else:
                line = trial
        if line:
            lines.append(line)
    return lines


def _advance(line: str, height: int, gap: int) -> int:
    """A blank line is a half-height spacer, not a full empty row."""
    return (height if line else height // 2) + gap


def _block_height(lines: list[str], font: ImageFont.FreeTypeFont, gap: int) -> int:
    height = _cap_height(font)
    return sum(_advance(line, height, gap) for line in lines)


def _draw_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    gap: int,
) -> int:
    height = _cap_height(font)
    top = font.getbbox("가")[1]
    for line in lines:
        if line:
            draw.text((x, y - top), line, font=font, fill=fill)
        y += _advance(line, height, gap)
    return y


def _fit_title(draw: ImageDraw.ImageDraw, lines: list[str], width: int, start: int, minimum: int):
    for size in range(start, minimum - 1, -2):
        font = _font(size)
        if all(_width(draw, line, font) <= width for line in lines):
            return font
    raise ValueError(f"title does not fit: {lines}")


def _furniture(canvas: Image.Image, spec: dict[str, Any], index: int, total: int, brand: str) -> ImageDraw.ImageDraw:
    # Every scrim must be down before the snapshot, or the audit measures a
    # backdrop the viewer never sees.
    if brand:
        _top_scrim(canvas, tint=SCRIM_TINT)
    rec.set_background(canvas)
    draw = ImageDraw.Draw(canvas)
    if brand:
        _brand(draw, brand)
        _record_brand(draw, brand)
    _page_pill(draw, index, total)
    _record_page(draw, index, total)
    return draw


BOTTOM_MARGIN = 104
INTERIOR_TOP = 670      # 모든 내지가 공유하는 고정 시작선
INTERIOR_FLOOR = 117    # 이 선 아래로는 글이 내려가지 않는다
KICKER_SIZE = 29
KICKER_TRACKING = 3
KICKER_GAP = 30         # 키커 -> 제목
POINT_GAP = 26          # 항목 사이
PROMPT_PAD_X = 70       # 프롬프트 박스 좌우 안쪽 여백
PROMPT_PAD_Y = 88       # 프롬프트 박스 위아래 안쪽 여백
PROMPT_GAP = 20         # 프롬프트 줄 사이
TITLE_BODY_GAP = 90     # 제목 -> 서브 카피


SCRIM_TINT = (13, 10, 22)        # 순수 검정 대신 아주 어두운 보라


def _veil(canvas: Image.Image, alpha: int) -> None:
    canvas.alpha_composite(Image.new("RGBA", CANVAS, SCRIM_TINT + (alpha,)))


BASE_ANCHOR = H - 130   # 짧은 블록의 밑변이 앉는 기준선 (하단 여백 ~130px)


def _interior_top(block_height: int) -> int:
    """Where an interior page's text block starts (its top y).

    A full-height block clings to the fixed start line (``INTERIOR_TOP``), which
    is what the eye tracks when swiping.  A *short* block, though, would leave
    the bottom of the card empty if it also started at that line — so it is
    bottom-anchored near ``BASE_ANCHOR`` and drops down the card instead.  The
    floor is still a hard limit: a very tall block is pulled up to respect it.
    Because the scrim starts a fixed lead above the block, dropping a short
    block also narrows its gradient automatically.
    """
    floor_top = H - INTERIOR_FLOOR - block_height
    bottom_anchored = BASE_ANCHOR - block_height
    fixed_line = min(INTERIOR_TOP, floor_top)
    return min(max(bottom_anchored, fixed_line), floor_top)


def _scrim(canvas: Image.Image, block_top: int, veil: int = 34, lead: int = 210) -> None:
    """Darken the photo just above the text block so dense copy stays legible
    while the upper half of the frame keeps its photograph.

    The flat veil unifies photographs but dulls a UI screenshot, so pages
    backed by a capture pass veil=0 and rely on the gradient alone.
    """
    if veil:
        _veil(canvas, veil)
    _gradient(
        canvas,
        start_y=max(260, block_top - lead),
        full_y=min(H - 2, block_top + 40),
        max_alpha=214,
        tail_alpha=240,
        tint=SCRIM_TINT,
    )


def _photo_canvas(source: Image.Image, spec: dict[str, Any]) -> Image.Image:
    """Interiors honour the same grade keys as the cover, so a bright daylight
    frame can be pulled into the deck's darker world."""
    return _photo(
        source,
        brightness=spec.get("grade_brightness", 1.0),
        saturation=spec.get("grade_saturation", 1.0),
        contrast=spec.get("grade_contrast", 1.0),
    )


CARD_TOP = 168
CARD_BOTTOM = 1280


def _head_height(draw: ImageDraw.ImageDraw, spec: dict[str, Any]) -> int:
    height = _kicker_height() if spec.get("badge") else 0
    lines = [line for line in spec["title"].splitlines() if line.strip()]
    font = _fit_title(draw, lines, W - MARGIN_X * 2, 82, 54)
    return height + len(lines) * (_cap_height(font) + 14)


def _card_head(draw: ImageDraw.ImageDraw, spec: dict[str, Any], y: int) -> int:
    """Badge + title at the top of a dark card.  Returns the next free y."""
    if spec.get("badge"):
        k_font = _font(KICKER_SIZE)
        rec.record(
            "kicker",
            (MARGIN_X, y, MARGIN_X + _width(draw, spec["badge"], k_font), y + _cap_height(k_font)),
            _accent(spec),
            KICKER_SIZE,
            text=spec["badge"],
        )
        y = _kicker(draw, spec["badge"], x=MARGIN_X, y=y, fill=_accent(spec))
    lines = [line for line in spec["title"].splitlines() if line.strip()]
    font = _fit_title(draw, lines, W - MARGIN_X * 2, 82, 54)
    height = _cap_height(font)
    title_top = y
    title_right = MARGIN_X + max((_width(draw, line, font) for line in lines), default=0)
    for line in lines:
        draw.text((MARGIN_X, y - font.getbbox("가")[1]), line, font=font, fill=WHITE)
        y += height + 14
    rec.record("title", (MARGIN_X, title_top, title_right, y - 14), WHITE, font.size, text=" ".join(lines))
    return y


def _card_start(total_height: int) -> int:
    """Optically centre a dark card's content between the furniture and the base."""
    span = CARD_BOTTOM - CARD_TOP
    return max(CARD_TOP, CARD_TOP + int((span - total_height) * 0.42))


def _points_height(draw: ImageDraw.ImageDraw, points: list[str], font, indent: int) -> int:
    height = 0
    for point in points:
        lines = _wrap(draw, point, font, W - MARGIN_X * 2 - indent)
        height += len(lines) * (_cap_height(font) + 12) + POINT_GAP
    return max(0, height - POINT_GAP)


def _photo_title_start(n_lines: int) -> int:
    """Shorter headlines get a bigger starting size: a one-liner reads as small
    at 84 on a full-bleed card, so it climbs toward the place-name scale while
    denser multi-line titles keep the current size.  ``_fit_title`` still shrinks
    to fit the width, so this only ever *raises* the ceiling."""
    return {1: 118, 2: 96}.get(n_lines, 84)


def _photo_story(source: Image.Image, spec: dict[str, Any], index: int, total: int, brand: str) -> Image.Image:
    canvas = _photo_canvas(source, spec)
    draw = ImageDraw.Draw(canvas)

    body = spec.get("body", "")
    body_font = _regular(37)
    body_lines = _wrap(draw, body, body_font, W - MARGIN_X * 2) if body else []
    # trailing gap after the last line would push the block up by one gap
    body_height = len(body_lines) * _cap_height(body_font) + max(0, len(body_lines) - 1) * 24

    lines = [line for line in spec["title"].splitlines() if line.strip()]
    title_font = _fit_title(draw, lines, W - MARGIN_X * 2, _photo_title_start(len(lines)), 54)
    title_height = len(lines) * (_cap_height(title_font) + 14)

    head = _kicker_height() if spec.get("badge") else 0
    block = head + title_height + ((TITLE_BODY_GAP + body_height) if body_lines else 0)
    block_top = _interior_top(block)
    _scrim(canvas, block_top, spec.get("veil", 34), spec.get("scrim_lead", 210))

    draw = _furniture(canvas, spec, index, total, brand)
    y = block_top
    if spec.get("badge"):
        k_font = _font(KICKER_SIZE)
        rec.record("kicker", (MARGIN_X, y, MARGIN_X + _width(draw, spec["badge"], k_font), y + _cap_height(k_font)),
                   _accent(spec), KICKER_SIZE, text=spec["badge"])
        y = _kicker(draw, spec["badge"], x=MARGIN_X, y=y, fill=_accent(spec))
    title_top = y
    title_right = MARGIN_X + max((_width(draw, line, title_font) for line in lines), default=0)
    y = _draw_block(draw, lines, x=MARGIN_X, y=y, font=title_font, fill=WHITE, gap=14)
    rec.record("title", (MARGIN_X, title_top, title_right, y), WHITE, title_font.size, text=" ".join(lines))
    if body_lines:
        body_top = y + TITLE_BODY_GAP
        body_right = MARGIN_X + max((_width(draw, line, body_font) for line in body_lines), default=0)
        body_end = _draw_block(draw, body_lines, x=MARGIN_X, y=body_top, font=body_font, fill=PAPER_DIM, gap=24)
        rec.record("body", (MARGIN_X, body_top, body_right, body_end), PAPER_DIM, body_font.size,
                   lines=len(body_lines), text=body)
    return canvas


def _prompt(source: Image.Image, spec: dict[str, Any], index: int, total: int, brand: str) -> Image.Image:
    canvas = _photo_canvas(source, spec)
    draw = ImageDraw.Draw(canvas)

    font = _regular(34)
    lines = _wrap(draw, spec["prompt"], font, W - MARGIN_X * 2 - PROMPT_PAD_X * 2)
    # _block_height carries a trailing gap after the last line; drop it so the
    # padding above and below the text is actually equal.
    box_height = _block_height(lines, font, PROMPT_GAP) - PROMPT_GAP + PROMPT_PAD_Y * 2

    note_font = _regular(34)
    note_lines = _wrap(draw, spec["body"], note_font, W - MARGIN_X * 2) if spec.get("body") else []
    note_height = (24 + len(note_lines) * (_cap_height(note_font) + 14)) if note_lines else 0

    head = _head_height(draw, spec)
    # A short prompt would leave the page bottom-heavy with dead space, so the
    # box grows to the floor and the text centres inside it.
    slack = (H - INTERIOR_FLOOR - INTERIOR_TOP) - (head + 18 + box_height + note_height)
    if slack > 0:
        box_height += slack
    block_top = _interior_top(head + 18 + box_height + note_height)
    _scrim(canvas, block_top, spec.get("veil", 34), spec.get("scrim_lead", 210))

    draw = _furniture(canvas, spec, index, total, brand)
    y = _card_head(draw, spec, block_top) + 18

    panel = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    pdraw.rounded_rectangle(
        (MARGIN_X, y, W - MARGIN_X, y + box_height),
        radius=28,
        fill=(14, 16, 21, 188),
        outline=(255, 255, 255, 56),
        width=2,
    )
    canvas.alpha_composite(panel)

    draw = ImageDraw.Draw(canvas)
    text_height = _block_height(lines, font, PROMPT_GAP) - PROMPT_GAP
    prompt_top = y + (box_height - text_height) // 2
    prompt_end = _draw_block(
        draw,
        lines,
        x=MARGIN_X + PROMPT_PAD_X,
        y=prompt_top,
        font=font,
        fill=WHITE,
        gap=PROMPT_GAP,
    )
    prompt_right = MARGIN_X + PROMPT_PAD_X + max((_width(draw, line, font) for line in lines), default=0)
    # Prompt copy sits on the translucent dark panel, not on the photo, and a
    # code/prompt block legitimately runs many lines -- so it is its own role,
    # outside the prose body's density budget.
    rec.record("prompt", (MARGIN_X + PROMPT_PAD_X, prompt_top, prompt_right, prompt_end), WHITE, font.size,
               lines=len(lines), bg_rgb=(14, 16, 21))
    if note_lines:
        _draw_block(draw, note_lines, x=MARGIN_X, y=y + box_height + 24, font=note_font, fill=_accent(spec), gap=14)
    return canvas


def _points(source: Image.Image, spec: dict[str, Any], index: int, total: int, brand: str) -> Image.Image:
    canvas = _photo_canvas(source, spec)
    draw = ImageDraw.Draw(canvas)

    font = _regular(40)
    num_font = _font(24)
    body_height = _points_height(draw, spec["points"], font, 96)
    block_top = _interior_top(_head_height(draw, spec) + 60 + body_height)
    _scrim(canvas, block_top, spec.get("veil", 34), spec.get("scrim_lead", 210))

    draw = _furniture(canvas, spec, index, total, brand)
    y = _card_head(draw, spec, block_top) + 60
    body_top = y
    body_right = MARGIN_X + 92
    total_lines = 0
    for number, point in enumerate(spec["points"], start=1):
        lines = _wrap(draw, point, font, W - MARGIN_X * 2 - 96)
        total_lines += len(lines)
        body_right = max(body_right, MARGIN_X + 92 + max((_width(draw, line, font) for line in lines), default=0))
        draw.ellipse((MARGIN_X + 4, y + 2, MARGIN_X + 44, y + 42), fill=_accent(spec))
        draw.text((MARGIN_X + 24, y + 22), str(number), font=num_font, fill=INK, anchor="mm")
        y = _draw_block(draw, lines, x=MARGIN_X + 92, y=y, font=font, fill=WHITE, gap=12) + POINT_GAP
    rec.record("body", (MARGIN_X, body_top, body_right, y - POINT_GAP), WHITE, font.size, lines=total_lines)
    return canvas


def _caution(source: Image.Image, spec: dict[str, Any], index: int, total: int, brand: str) -> Image.Image:
    canvas = _photo_canvas(source, spec)
    draw = ImageDraw.Draw(canvas)

    font = _regular(40)
    body_height = _points_height(draw, spec["points"], font, 72)
    block_top = _interior_top(_head_height(draw, spec) + 60 + body_height)
    _scrim(canvas, block_top, spec.get("veil", 34), spec.get("scrim_lead", 210))

    draw = _furniture(canvas, spec, index, total, brand)
    y = _card_head(draw, spec, block_top) + 60
    body_top = y
    body_right = MARGIN_X + 68
    total_lines = 0
    for point in spec["points"]:
        lines = _wrap(draw, point, font, W - MARGIN_X * 2 - 72)
        total_lines += len(lines)
        body_right = max(body_right, MARGIN_X + 68 + max((_width(draw, line, font) for line in lines), default=0))
        draw.rounded_rectangle((MARGIN_X + 6, y + 10, MARGIN_X + 26, y + 30), radius=6, fill=_accent(spec))
        y = _draw_block(draw, lines, x=MARGIN_X + 68, y=y, font=font, fill=WHITE, gap=12) + POINT_GAP
    rec.record("body", (MARGIN_X, body_top, body_right, y - POINT_GAP), WHITE, font.size, lines=total_lines)
    return canvas


def _outro(source: Image.Image, spec: dict[str, Any], index: int, total: int, brand: str) -> Image.Image:
    """Closing brand card: smaller headline, an accent-coloured brand line and a
    follow button, so the last slide reads as a call to action rather than one
    more paragraph."""
    canvas = _photo_canvas(source, spec)
    _gradient(canvas, start_y=330, full_y=900, max_alpha=252)
    draw = _furniture(canvas, spec, index, total, brand)
    accent = _accent(spec)

    lines = [line for line in spec["title"].splitlines() if line.strip()]
    font = _fit_title(draw, lines, W - MARGIN_X * 2, 92, 58)
    line_h = _cap_height(font)
    top = font.getbbox("가")[1]

    body_font = _regular(34)
    body_lines = _wrap(draw, spec["body"], body_font, W - MARGIN_X * 2) if spec.get("body") else []

    button = spec.get("button")
    btn_font = _font(36)
    btn_h, btn_pad = 92, 54
    btn_w = (draw.textbbox((0, 0), button, font=btn_font)[2] + btn_pad * 2) if button else 0

    handle = spec.get("handle")
    handle_font = _font(30)

    block = len(lines) * (line_h + 18)
    if body_lines:
        block += 26 + len(body_lines) * (_cap_height(body_font) + 14)
    if button:
        block += 58 + btn_h
    if handle:
        block += 26 + _cap_height(handle_font)

    y = 742 - block // 2
    if spec.get("badge"):
        bf = _font(26)
        w = sum(_width(draw, c, bf) for c in spec["badge"]) + 2 * (len(spec["badge"]) - 1) + 52
        _badge(draw, spec["badge"], x=(W - w) // 2, y=y - 44 - 56, fill=None)

    title_top = y
    title_w = max((_width(draw, line, font) for line in lines), default=0)
    for i, line in enumerate(lines):
        fill = accent if i == len(lines) - 1 and len(lines) > 1 else WHITE
        draw.text(((W - _width(draw, line, font)) // 2, y - top), line, font=font, fill=fill)
        y += line_h + 18
    rec.record("title", ((W - title_w) // 2, title_top, (W + title_w) // 2, y - 18), WHITE, font.size,
               text=" ".join(lines))

    if body_lines:
        y += 26
        body_top = y
        body_w = max((_width(draw, line, body_font) for line in body_lines), default=0)
        for line in body_lines:
            draw.text(((W - _width(draw, line, body_font)) // 2, y), line, font=body_font, fill=PAPER_DIM)
            y += _cap_height(body_font) + 14
        rec.record("body", ((W - body_w) // 2, body_top, (W + body_w) // 2, y), PAPER_DIM, body_font.size,
                   lines=len(body_lines), text=spec.get("body", ""))

    if button:
        y += 58
        x = (W - btn_w) // 2
        draw.rounded_rectangle((x, y, x + btn_w, y + btn_h), radius=btn_h // 2, fill=accent)
        draw.text((W // 2, y + btn_h // 2), button, font=btn_font, fill=INK, anchor="mm")
        y += btn_h

    if handle:
        y += 26
        draw.text(((W - _width(draw, handle, handle_font)) // 2, y), handle, font=handle_font, fill=PAPER_DIM)
    return canvas


def _brandcard(source: Image.Image | None, spec: dict[str, Any], index: int, total: int, brand: str) -> Image.Image:
    """Minimal closing card: wordmark, one action line, handle.

    No photograph and no repeated brand name in the headline -- the wordmark
    carries the name once, the handle repeats it only as an address.
    """
    canvas = Image.new("RGBA", CANVAS, INK + (255,))
    if source is not None:
        canvas = _photo_canvas(source, spec)
        _veil(canvas, spec.get("veil", 215))
    rec.set_background(canvas)
    draw = ImageDraw.Draw(canvas)
    accent = _accent(spec)

    mark_font = _font(spec.get("mark_size", 50))
    mark_w = sum(_width(draw, c, mark_font) for c in brand) + 8 * max(0, len(brand) - 1)

    lines = [line for line in spec["title"].splitlines() if line.strip()]
    font = _fit_title(draw, lines, W - MARGIN_X * 2, 68, 44)
    line_h = _cap_height(font)
    top = font.getbbox("가")[1]

    handle = spec.get("handle")
    handle_font = _font(30)

    block = _cap_height(mark_font) + 64 + len(lines) * (line_h + 20)
    if handle:
        block += 86 + _cap_height(handle_font)
    y = (H - block) // 2

    _draw_tracked(draw, brand, x=(W - mark_w) // 2, y=y - mark_font.getbbox("가")[1],
                  font=mark_font, tracking=8, fill=WHITE)
    y += _cap_height(mark_font) + 64

    title_top = y
    title_w = max((_width(draw, line, font) for line in lines), default=0)
    for line in lines:
        draw.text(((W - _width(draw, line, font)) // 2, y - top), line, font=font, fill=WHITE)
        y += line_h + 20
    rec.record("title", ((W - title_w) // 2, title_top, (W + title_w) // 2, y - 20), WHITE, font.size,
               text=" ".join(lines))

    if handle:
        y += 86
        draw.text(((W - _width(draw, handle, handle_font)) // 2, y), handle, font=handle_font, fill=accent)
    return canvas


LAYOUTS = {
    "photo_story": _photo_story,
    "brandcard": _brandcard,
    "prompt": _prompt,
    "points": _points,
    "caution": _caution,
    "outro": _outro,
}
PHOTO_LAYOUTS = {"photo_story", "prompt", "points", "caution", "outro"}


# Text may sit anywhere from the brand line near the top edge to a block pulled
# almost to the floor, so the safe area is generous; _fit_title already caps
# headline width, so this mainly catches copy that escapes the canvas.
SAFE_AREA = (50, 40, W - 50, H - 40)


def _write_manifest(target: Path, index: int, elements: list[dict]) -> None:
    manifest = target.with_suffix(".layout.json")
    payload = {
        "slide": index,
        "canvas": list(CANVAS),
        "safe_area": list(SAFE_AREA),
        "card": str(target.resolve()),
        "elements": elements,
    }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def compose_carousel(spec_path: Path, backgrounds: dict[str, Path], output: Path) -> list[Path]:
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    slides = payload["slides"]
    if not 1 <= len(slides) <= 10:
        raise ValueError("Instagram carousel must have 1-10 slides")
    total = payload.get("total", len(slides))
    brand = payload.get("brand", "")
    accent = payload.get("accent")
    written: list[Path] = []

    for index, spec in enumerate(slides, start=1):
        if accent and "accent" not in spec:
            spec = {**spec, "accent": accent}
        target = output / f"{index:02d}.jpg"
        layout = spec.get("layout")
        rec.start()
        try:
            if layout == "cover":
                compose_cover(
                    source=backgrounds[spec["slide_id"]],
                    spec={**spec, "brand": brand},
                    index=index,
                    total=total,
                    output=target,
                )
            elif layout not in LAYOUTS:
                raise ValueError(f"unknown tips layout: {layout}")
            else:
                source = None
                if layout in PHOTO_LAYOUTS:
                    path = backgrounds.get(spec["slide_id"])
                    if path is None or not Path(path).is_file():
                        raise FileNotFoundError(f"{spec['slide_id']} needs a background photo")
                    with Image.open(path) as opened:
                        source = opened.copy()
                image = LAYOUTS[layout](source, spec, index, total, brand)
                target.parent.mkdir(parents=True, exist_ok=True)
                image.convert("RGB").save(target, "JPEG", quality=96, subsampling=0, optimize=True, progressive=True)
            elements = rec.finish()
        finally:
            if rec.active():  # a raised error left the recorder open
                rec.finish()
        _write_manifest(target, index, elements)
        written.append(target)
    return written
