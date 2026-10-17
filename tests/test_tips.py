import json
from pathlib import Path

import pytest
from PIL import Image

from instacards.editorial import CANVAS
from instacards.tips import compose_carousel


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
