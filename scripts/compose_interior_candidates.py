#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from instacards.editorial import compose_editorial_slide
from instacards.qc import make_contact_sheet


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose each interior FLUX candidate with final copy")
    parser.add_argument("copy", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.copy.read_text(encoding="utf-8"))
    slides = {item["slide_id"]: item for item in payload["slides"]}
    for slide_dir in sorted(path for path in args.candidates.iterdir() if path.is_dir()):
        spec = slides[slide_dir.name]
        target = args.output / slide_dir.name
        for source in sorted(slide_dir.glob("*.jpg")):
            index = int(slide_dir.name[1:])
            compose_editorial_slide(
                source=source,
                spec=spec,
                index=index,
                total=len(slides),
                output=target / source.name,
            )
        make_contact_sheet(target, args.output / f"{slide_dir.name}-sheet.jpg", columns=2)


if __name__ == "__main__":
    main()
