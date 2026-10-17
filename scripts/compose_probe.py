#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from instacards.probe import compose_probe_carousel


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a three-role editorial probe")
    parser.add_argument("spec", type=Path)
    parser.add_argument("backgrounds", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    compose_probe_carousel(args.spec, args.backgrounds, args.output)


if __name__ == "__main__":
    main()
