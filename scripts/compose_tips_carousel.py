#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from instacards.qc import make_contact_sheet
from instacards.tips import compose_carousel


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose the full AI-tips carousel")
    parser.add_argument("spec", type=Path)
    parser.add_argument("backgrounds", type=Path, help="slide_id -> 이미지 경로 매핑 JSON")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    mapping = {k: Path(v) for k, v in json.loads(args.backgrounds.read_text(encoding="utf-8")).items()}
    cards = args.output / "cards"
    written = compose_carousel(args.spec, mapping, cards)
    make_contact_sheet(cards, args.output / "contact-sheet.jpg", columns=4)
    for path in written:
        print(f"WROTE {path}")


if __name__ == "__main__":
    main()
