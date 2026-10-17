#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from instacards.cover import compose_cover_set
from instacards.qc import make_contact_sheet


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose headline candidates over one cover background")
    parser.add_argument("spec", type=Path)
    parser.add_argument("background", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cards = args.output / "cards"
    written = compose_cover_set(args.spec, args.background, cards)
    make_contact_sheet(cards, args.output / "contact-sheet.jpg", columns=3)
    for path in written:
        print(f"WROTE {path}")


if __name__ == "__main__":
    main()
