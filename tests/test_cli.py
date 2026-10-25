from __future__ import annotations

import json
from pathlib import Path

from instacards.cli import main


def _write_campaign(tmp_path: Path) -> Path:
    campaign_path = tmp_path / "campaign.json"
    campaign_path.write_text(
        json.dumps({
            "slug": "audit-demo",
            "theme": {"brand": "TEST LAB"},
            "slides": [
                {"headline": "첫 번째 제목", "body": "짧은 본문 한 줄.", "prompt": "P1"},
                {"headline": "두 번째 제목", "body": "역시 짧은 본문.", "prompt": "P2"},
            ],
        }),
        encoding="utf-8",
    )
    return campaign_path


def test_render_draft_writes_layout_manifests(tmp_path: Path) -> None:
    campaign_path = _write_campaign(tmp_path)
    root = tmp_path / "out"

    assert main(["render", str(campaign_path), "--output-dir", str(root), "--draft"]) == 0

    cards = root / "audit-demo" / "draft" / "cards"
    assert sorted(p.name for p in cards.glob("*.layout.json")) == ["01.layout.json", "02.layout.json"]


def test_audit_passes_on_clean_draft_deck(tmp_path: Path) -> None:
    campaign_path = _write_campaign(tmp_path)
    root = tmp_path / "out"
    main(["render", str(campaign_path), "--output-dir", str(root), "--draft"])

    assert main(["audit", str(campaign_path), "--output-dir", str(root), "--draft"]) == 0


def test_audit_fails_when_rules_make_every_card_red(tmp_path: Path) -> None:
    campaign_path = _write_campaign(tmp_path)
    root = tmp_path / "out"
    main(["render", str(campaign_path), "--output-dir", str(root), "--draft"])
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps({"min_contrast_large": 25.0}), encoding="utf-8")

    exit_code = main([
        "audit", str(campaign_path),
        "--output-dir", str(root),
        "--draft",
        "--rules", str(rules_path),
    ])

    assert exit_code == 1
