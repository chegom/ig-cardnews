from __future__ import annotations

import json
from pathlib import Path

from instacards.audit import audit_card, audit_deck, contrast_ratio, load_rules


def test_contrast_ratio_black_on_white_is_maximum() -> None:
    assert round(contrast_ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0


def _manifest(**element_overrides: object) -> dict:
    element = {
        "role": "title",
        "text": "읽히는 제목",
        "bbox": [92, 200, 900, 360],
        "color": "#FFFFFF",
        "bg_rgb": [12, 14, 20],
        "font_px": 80,
    }
    element.update(element_overrides)
    return {
        "slide": 1,
        "canvas": [1080, 1350],
        "safe_area": [92, 60, 988, 1290],
        "elements": [element],
    }


def test_low_contrast_text_is_flagged_red() -> None:
    manifest = _manifest(color="#FFFFFF", bg_rgb=[240, 240, 240])

    findings = audit_card(manifest)

    contrast = [f for f in findings if f.code == "contrast"]
    assert len(contrast) == 1
    assert contrast[0].level == "red"
    assert contrast[0].slide == 1
    assert contrast[0].role == "title"


def test_high_contrast_text_produces_no_contrast_finding() -> None:
    manifest = _manifest(color="#FFFFFF", bg_rgb=[12, 14, 20])

    findings = audit_card(manifest)

    assert [f for f in findings if f.code == "contrast"] == []


def test_text_past_safe_area_is_flagged_red_overflow() -> None:
    manifest = _manifest(bbox=[92, 200, 1010, 360])  # right edge 1010 > safe right 988

    findings = audit_card(manifest)

    overflow = [f for f in findings if f.code == "overflow"]
    assert len(overflow) == 1
    assert overflow[0].level == "red"


def test_text_inside_safe_area_produces_no_overflow_finding() -> None:
    manifest = _manifest(bbox=[92, 200, 900, 360])

    findings = audit_card(manifest)

    assert [f for f in findings if f.code == "overflow"] == []


def test_overcrowded_body_is_flagged_red_density() -> None:
    manifest = _manifest(role="body", color="#EEF0F4", font_px=35, lines=7)

    findings = audit_card(manifest)

    density = [f for f in findings if f.code == "density"]
    assert len(density) == 1
    assert density[0].level == "red"


def test_body_within_line_budget_produces_no_density_finding() -> None:
    manifest = _manifest(role="body", color="#EEF0F4", font_px=35, lines=5)

    findings = audit_card(manifest)

    assert [f for f in findings if f.code == "density"] == []


def _clean_manifest(slide: int) -> dict:
    return {
        "slide": slide,
        "canvas": [1080, 1350],
        "safe_area": [92, 60, 988, 1290],
        "elements": [
            {"role": "title", "text": "제목", "bbox": [92, 200, 900, 360], "color": "#FFFFFF", "bg_rgb": [12, 14, 20], "font_px": 80},
            {"role": "brand", "text": "BRAND", "bbox": [92, 1245, 300, 1275], "color": "#FFFFFF", "bg_rgb": [10, 10, 12], "font_px": 26},
            {"role": "page", "text": "1 — 3", "bbox": [880, 1245, 988, 1275], "color": "#D7FF3F", "bg_rgb": [10, 10, 12], "font_px": 26},
        ],
    }


def test_deck_with_a_red_card_fails_the_gate() -> None:
    clean = _clean_manifest(1)
    broken = _clean_manifest(2)
    broken["elements"][0]["bg_rgb"] = [240, 240, 240]  # white title on near-white → red contrast

    report = audit_deck([clean, broken])

    assert report.ok is False
    assert report.exit_code == 1
    assert report.worst_level == "red"
    assert any(f.slide == 2 and f.code == "contrast" for f in report.findings)


def test_clean_deck_passes_the_gate() -> None:
    report = audit_deck([_clean_manifest(1), _clean_manifest(2)])

    assert report.ok is True
    assert report.exit_code == 0
    assert report.worst_level == "green"


def test_inconsistent_footer_position_is_flagged_yellow_furniture() -> None:
    first = _clean_manifest(1)
    drifted = _clean_manifest(2)
    # page number drifts far up on slide 2
    drifted["elements"][2]["bbox"] = [880, 1000, 988, 1030]

    report = audit_deck([first, drifted])

    furniture = [f for f in report.findings if f.code == "furniture"]
    assert len(furniture) >= 1
    assert all(f.level == "yellow" for f in furniture)


def test_load_rules_overrides_defaults(tmp_path: Path) -> None:
    rules_path = tmp_path / "audit_rules.json"
    rules_path.write_text(json.dumps({"min_contrast_body": 7.0}), encoding="utf-8")

    rules = load_rules(rules_path)

    assert rules.min_contrast_body == 7.0
    assert rules.min_contrast_large == 3.0  # untouched default


def test_report_to_dict_summarises_findings() -> None:
    broken = _clean_manifest(1)
    broken["elements"][0]["bg_rgb"] = [240, 240, 240]

    payload = audit_deck([broken]).to_dict()

    assert payload["ok"] is False
    assert payload["worst_level"] == "red"
    assert payload["exit_code"] == 1
    assert payload["findings"][0]["code"] == "contrast"
    assert payload["counts"]["red"] >= 1
