#!/usr/bin/env python3
"""Turn a product screenshot into a carousel background.

The compositor scrims the lower half for copy, so a raw full-page capture would
bury the UI. This mats a crop of the screenshot into the upper area of a dark
canvas, leaving clean space underneath for the headline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

CANVAS = (1080, 1350)
W, H = CANVAS


def build(
    source: Path,
    box: tuple[int, int, int, int],
    target: Path,
    *,
    top: int,
    bg: tuple[int, int, int],
    width: int = W - 96,
    highlight: tuple[int, int, int, int] | None = None,
    dim: int = 108,
    ring: tuple[int, int, int] = (139, 124, 246),
) -> None:
    """Mat a crop onto the canvas.

    The compositor's scrim starts fading around y=460, so a panel that reaches
    past it loses its bottom rows.  Narrowing the panel shortens it, which is
    what keeps the screenshot intact rather than half-dissolved.
    """
    with Image.open(source) as opened:
        crop = opened.convert("RGB").crop(box)

    scale = width / crop.width
    height = round(crop.height * scale)
    crop = crop.resize((width, height), Image.Resampling.LANCZOS)
    left = (W - width) // 2

    if highlight is not None:
        # Same window on every page; only the region under discussion stays lit.
        hx1 = round((highlight[0] - box[0]) * scale)
        hy1 = round((highlight[1] - box[1]) * scale)
        hx2 = round((highlight[2] - box[0]) * scale)
        hy2 = round((highlight[3] - box[1]) * scale)
        veil = Image.new("RGBA", (width, height), (10, 10, 16, dim))
        ImageDraw.Draw(veil).rounded_rectangle((hx1, hy1, hx2, hy2), radius=14, fill=(0, 0, 0, 0))
        crop = Image.alpha_composite(crop.convert("RGBA"), veil).convert("RGB")
        ImageDraw.Draw(crop).rounded_rectangle((hx1, hy1, hx2, hy2), radius=14, outline=ring, width=4)

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=22, fill=255)

    canvas = Image.new("RGB", CANVAS, bg)
    shadow = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (left, top + 14, left + width, top + height + 14), radius=22, fill=(0, 0, 0, 150)
    )
    canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(18))).convert("RGB"), (0, 0))
    canvas.paste(crop, (left, top), mask)

    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, "JPEG", quality=95, subsampling=0, optimize=True)
    print(f"WROTE {target}  (crop {crop.size})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mat screenshot crops into carousel backgrounds")
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    bg = tuple(plan.get("background", [14, 12, 22]))
    for slide_id, item in plan["shots"].items():
        build(
            Path(item["source"]),
            tuple(item["box"]),
            args.output / slide_id / "1.jpg",
            top=item.get("top", 150),
            bg=bg,
            width=item.get("width", W - 96),
            highlight=tuple(item["highlight"]) if item.get("highlight") else None,
        )


if __name__ == "__main__":
    main()
