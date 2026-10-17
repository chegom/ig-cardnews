#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from instacards.editorial import compose_editorial_carousel


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a multi-layout educational carousel")
    parser.add_argument("spec", type=Path)
    parser.add_argument("backgrounds", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    compose_editorial_carousel(args.spec, args.backgrounds, args.output)


if __name__ == "__main__":
    main()
