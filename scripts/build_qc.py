#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from instacards.qc import build_manifest, make_contact_sheet


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a carousel manifest and contact sheet")
    parser.add_argument("cards", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    build_manifest(args.cards, args.output / "manifest.json")
    make_contact_sheet(args.cards, args.output / "contact-sheet.jpg")


if __name__ == "__main__":
    main()
