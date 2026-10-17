"""Technical manifests and contact sheets for review gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from instacards.editorial import BOLD_FONT, CANVAS, INK, PAPER


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def contact_sheet_label(path: Path) -> str:
    """Return the slide identifier encoded in the card filename."""
    return path.stem


def build_manifest(cards: Path, output: Path) -> dict:
    items = []
    mobile_dir = output.parent / "mobile"
    mobile_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(cards.glob("*.jpg")):
        with Image.open(path) as image:
            width, height = image.size
            mobile = ImageOps.fit(image.convert("RGB"), (360, 450), Image.Resampling.LANCZOS)
            mobile_path = mobile_dir / path.name
            mobile.save(mobile_path, "JPEG", quality=92, optimize=True)
            item = {
                "slide_id": f"s{int(path.stem):02d}",
                "path": str(path.resolve()),
                "sha256": _sha256(path),
                "mime": "image/jpeg",
                "width": width,
                "height": height,
                "mode": image.mode,
                "preview_360x450": str(mobile_path.resolve()),
                "technical_pass": (width, height) == CANVAS and image.mode == "RGB",
            }
            items.append(item)
    manifest = {"schema_version": "artifact_manifest.v1", "items": items}
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    manifest["manifest_hash"] = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def make_contact_sheet(cards: Path, output: Path, *, columns: int = 4) -> None:
    paths = sorted(cards.glob("*.jpg"))
    if not paths:
        raise ValueError(f"no JPEG cards found in {cards}")
    thumb = (240, 300)
    gutter = 20
    label_h = 42
    rows = (len(paths) + columns - 1) // columns
    width = gutter + columns * (thumb[0] + gutter)
    height = gutter + rows * (thumb[1] + label_h + gutter)
    sheet = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(BOLD_FONT), 22)
    for position, path in enumerate(paths):
        row, col = divmod(position, columns)
        x = gutter + col * (thumb[0] + gutter)
        y = gutter + row * (thumb[1] + label_h + gutter)
        with Image.open(path) as image:
            preview = ImageOps.fit(image.convert("RGB"), thumb, Image.Resampling.LANCZOS)
        sheet.paste(preview, (x, y))
        draw.text((x, y + thumb[1] + 9), contact_sheet_label(path), font=font, fill=INK)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, "JPEG", quality=92, optimize=True)
