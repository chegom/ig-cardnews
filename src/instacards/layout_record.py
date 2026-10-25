"""A small, process-local recorder so the full-bleed compositors can emit the
same layout manifest schema that :mod:`instacards.audit` consumes.

The compositors in :mod:`instacards.tips` and :mod:`instacards.cover` draw text
in many places with no single chokepoint, so instead of threading a recorder
through every function signature we keep one active recorder per card.  A card
renders start-to-finish synchronously, so a module-level recorder is safe here.

Usage per card::

    layout_record.start()
    ...                                  # a compositor draws the card
    elements = layout_record.finish()    # list[dict] for the manifest

Inside a compositor, snapshot the background *after* the scrim/gradient but
*before* any glyphs land, then record each text element::

    layout_record.set_background(canvas)
    layout_record.record("title", bbox, WHITE, font.size)
"""

from __future__ import annotations

from PIL import Image, ImageStat

_elements: list[dict] | None = None
_background: Image.Image | None = None


def start() -> None:
    global _elements, _background
    _elements = []
    _background = None


def active() -> bool:
    return _elements is not None


def set_background(canvas: Image.Image) -> None:
    """Remember the pixels behind the text so contrast is measured honestly."""
    global _background
    if _elements is not None:
        _background = canvas.convert("RGB")


def finish() -> list[dict]:
    global _elements, _background
    recorded = _elements or []
    _elements = None
    _background = None
    return recorded


def _to_hex(color: object) -> str:
    if isinstance(color, str):
        return color.upper()
    red, green, blue = color[0], color[1], color[2]  # type: ignore[index]
    return f"#{red:02X}{green:02X}{blue:02X}"


def _mean_rgb(box: list[int]) -> list[int]:
    if _background is None:
        return [0, 0, 0]
    width, height = _background.size
    left = max(0, min(box[0], width - 1))
    top = max(0, min(box[1], height - 1))
    right = max(left + 1, min(box[2], width))
    bottom = max(top + 1, min(box[3], height))
    region = _background.crop((left, top, right, bottom))
    return [round(channel) for channel in ImageStat.Stat(region).mean[:3]]


def record(role: str, bbox, color: object, font_px: int, *, bg_rgb=None, **extra) -> None:
    """Append one text element.  No-op unless a recorder is active.

    ``bg_rgb`` overrides the sampled background — use it for text that sits on
    its own backing (a page pill, a prompt panel) rather than on the photo.
    """
    if _elements is None:
        return
    box = [int(round(v)) for v in bbox]
    _elements.append(
        {
            "role": role,
            "bbox": box,
            "color": _to_hex(color),
            "bg_rgb": list(bg_rgb) if bg_rgb is not None else _mean_rgb(box),
            "font_px": int(font_px),
            **extra,
        }
    )
