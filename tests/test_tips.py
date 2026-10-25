import json
from pathlib import Path

import pytest
from PIL import Image

from instacards.audit import AuditRules, audit_directory
from instacards.editorial import CANVAS
from instacards.tips import INTERIOR_FLOOR, INTERIOR_TOP, _interior_top, compose_carousel

_H = CANVAS[1]


def _background(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 1280), (130, 120, 110)).save(path, "JPEG", quality=92)
    return path


def _payload() -> dict:
    return {
        "total": 4,
        "brand": "AI TREND",
        "slides": [
            {"slide_id": "s01", "layout": "cover", "badge": "AI TIPS | GENERAL", "title": "책 한 권,\n10분이면 끝"},
            {"slide_id": "s02", "layout": "photo_story", "badge": "왜", "title": "사둔 책은\n쌓이는데", "body": "진입 비용이 문제입니다."},
            {"slide_id": "s03", "layout": "prompt", "badge": "핵심", "title": "이 한 줄", "prompt": "'[책]'을 읽으려고 해.\n1. 통념\n2. 근거", "body": "결과가 다릅니다."},
            {"slide_id": "s04", "layout": "points", "badge": "왜", "title": "구조를 묻기 때문", "points": ["통념을 묻는다", "근거를 묻는다"]},
        ],
    }


def test_carousel_writes_one_card_per_slide(tmp_path: Path) -> None:
    spec = tmp_path / "copy.json"
    spec.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")
    photo = _background(tmp_path / "bg.jpg")
    written = compose_carousel(spec, {f"s0{i}": photo for i in range(1, 5)}, tmp_path / "cards")

    assert [p.name for p in written] == ["01.jpg", "02.jpg", "03.jpg", "04.jpg"]
    for path in written:
        with Image.open(path) as image:
            assert image.size == CANVAS


def test_carousel_writes_layout_manifest_per_card(tmp_path: Path) -> None:
    spec = tmp_path / "copy.json"
    spec.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")
    photo = _background(tmp_path / "bg.jpg")
    cards = tmp_path / "cards"

    compose_carousel(spec, {f"s0{i}": photo for i in range(1, 5)}, cards)

    manifests = sorted(p.name for p in cards.glob("*.layout.json"))
    assert manifests == ["01.layout.json", "02.layout.json", "03.layout.json", "04.layout.json"]
    first = json.loads((cards / "01.layout.json").read_text(encoding="utf-8"))
    assert first["slide"] == 1
    assert first["canvas"] == list(CANVAS)
    roles = {element["role"] for element in first["elements"]}
    assert "title" in roles


def test_carousel_audit_passes_on_dark_scrimmed_deck(tmp_path: Path) -> None:
    spec = tmp_path / "copy.json"
    spec.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")
    photo = _background(tmp_path / "bg.jpg")
    cards = tmp_path / "cards"
    compose_carousel(spec, {f"s0{i}": photo for i in range(1, 5)}, cards)

    report = audit_directory(cards)

    assert report.worst_level != "red"


def test_carousel_audit_flags_red_under_strict_contrast(tmp_path: Path) -> None:
    spec = tmp_path / "copy.json"
    spec.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")
    photo = _background(tmp_path / "bg.jpg")
    cards = tmp_path / "cards"
    compose_carousel(spec, {f"s0{i}": photo for i in range(1, 5)}, cards)

    report = audit_directory(cards, AuditRules(min_contrast_large=25.0, min_contrast_body=25.0))

    assert report.ok is False


def test_short_block_drops_toward_the_base() -> None:
    # A short copy block should sit lower on the card (larger y) instead of
    # clinging to the old fixed start line and leaving the bottom empty.
    assert _interior_top(200) > INTERIOR_TOP


def test_block_that_spans_to_the_floor_keeps_the_fixed_start() -> None:
    span = (_H - INTERIOR_FLOOR) - INTERIOR_TOP
    assert _interior_top(span) == INTERIOR_TOP


def test_very_tall_block_is_pulled_up_to_respect_the_floor() -> None:
    span = (_H - INTERIOR_FLOOR) - INTERIOR_TOP
    tall = span + 80
    assert _interior_top(tall) == _H - INTERIOR_FLOOR - tall


def test_short_single_line_headline_gets_a_larger_title(tmp_path: Path) -> None:
    payload = {
        "total": 1,
        "brand": "LAB",
        "slides": [{"slide_id": "s01", "layout": "photo_story", "title": "성수 카페", "body": "짧은 한 줄."}],
    }
    spec = tmp_path / "copy.json"
    spec.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    photo = _background(tmp_path / "bg.jpg")
    cards = tmp_path / "cards"
    compose_carousel(spec, {"s01": photo}, cards)

    manifest = json.loads((cards / "01.layout.json").read_text(encoding="utf-8"))
    title = next(e for e in manifest["elements"] if e["role"] == "title")
    assert title["font_px"] >= 100


def test_photo_layout_requires_a_background(tmp_path: Path) -> None:
    payload = _payload()
    spec = tmp_path / "copy.json"
    spec.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    photo = _background(tmp_path / "bg.jpg")
    with pytest.raises(FileNotFoundError, match="s02"):
        compose_carousel(spec, {"s01": photo}, tmp_path / "cards")


def test_unknown_layout_is_rejected(tmp_path: Path) -> None:
    payload = _payload()
    payload["slides"][3]["layout"] = "mystery"
    spec = tmp_path / "copy.json"
    spec.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    photo = _background(tmp_path / "bg.jpg")
    with pytest.raises(ValueError, match="unknown tips layout"):
        compose_carousel(spec, {f"s0{i}": photo for i in range(1, 5)}, tmp_path / "cards")


def test_carousel_rejects_more_than_ten_slides(tmp_path: Path) -> None:
    payload = _payload()
    payload["slides"] = payload["slides"] * 3
    spec = tmp_path / "copy.json"
    spec.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    photo = _background(tmp_path / "bg.jpg")
    with pytest.raises(ValueError, match="1-10 slides"):
        compose_carousel(spec, {f"s0{i}": photo for i in range(1, 5)}, tmp_path / "cards")
