#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from instacards.editorial import compose_editorial_slide
from instacards.qc import make_contact_sheet


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose identical copy over cover candidates")
    parser.add_argument("copy", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.copy.read_text(encoding="utf-8"))
    spec = payload["slides"][0]
    cards = args.output / "cards"
    for index, source in enumerate(sorted(args.candidates.glob("*.jpg")), start=1):
        compose_editorial_slide(source=source, spec=spec, index=1, total=8, output=cards / f"{index:02d}.jpg")
    make_contact_sheet(cards, args.output / "contact-sheet.jpg", columns=2)


if __name__ == "__main__":
    main()
