#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from instacards.audit import audit_directory, load_rules
from instacards.qc import make_contact_sheet
from instacards.tips import compose_carousel


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose the full AI-tips carousel")
    parser.add_argument("spec", type=Path)
    parser.add_argument("backgrounds", type=Path, help="slide_id -> 이미지 경로 매핑 JSON")
    parser.add_argument("output", type=Path)
    parser.add_argument("--audit", action="store_true", help="합성 후 비주얼 품질 감사, 빨강이면 종료코드 1")
    parser.add_argument("--rules", type=Path, default=None, help="audit_rules.json 임계값 덮어쓰기")
    args = parser.parse_args()

    mapping = {k: Path(v) for k, v in json.loads(args.backgrounds.read_text(encoding="utf-8")).items()}
    cards = args.output / "cards"
    written = compose_carousel(args.spec, mapping, cards)
    make_contact_sheet(cards, args.output / "contact-sheet.jpg", columns=4)
    for path in written:
        print(f"WROTE {path}")

    if args.audit:
        report = audit_directory(cards, load_rules(args.rules))
        print(report.to_text(), file=sys.stderr)
        return report.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
