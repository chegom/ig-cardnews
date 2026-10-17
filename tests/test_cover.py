import json
from pathlib import Path

import pytest
from PIL import Image

from instacards.cover import compose_cover, compose_cover_set
from instacards.editorial import CANVAS


def _background(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 1280), (120, 140, 160)).save(path, "JPEG", quality=92)
    return path


def _payload() -> dict:
    return {
        "total": 8,
        "brand": "AI TREND",
        "badge": "AI TIPS | GENERAL",
        "candidates": [
            {"candidate_id": "h1", "title": "책 한 권 읽기,\n이 명령어 한 줄이면 끝!"},
            {"candidate_id": "h2", "title": "300쪽짜리 책 한 권,\n10분이면 다 읽습니다"},
        ],
    }


def test_cover_set_writes_one_card_per_candidate(tmp_path: Path) -> None:
    background = _background(tmp_path / "bg.jpg")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")

    written = compose_cover_set(spec, background, tmp_path / "cards")

    assert [path.name for path in written] == ["01.jpg", "02.jpg"]
    for path in written:
        with Image.open(path) as image:
            assert image.size == CANVAS


def test_cover_inherits_shared_brand_and_badge(tmp_path: Path) -> None:
    background = _background(tmp_path / "bg.jpg")
    payload = _payload()
    payload["candidates"][0]["badge"] = "AI TIPS | PROMPT"
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    first, second = compose_cover_set(spec, background, tmp_path / "cards")

    with Image.open(first) as a, Image.open(second) as b:
        assert a.tobytes() != b.tobytes()


def test_cover_rejects_empty_title(tmp_path: Path) -> None:
    background = _background(tmp_path / "bg.jpg")
    with pytest.raises(ValueError, match="requires a title"):
        compose_cover(
            source=background, spec={"title": ""}, index=1, total=8, output=tmp_path / "out.jpg"
        )


def test_cover_rejects_four_line_headline(tmp_path: Path) -> None:
    background = _background(tmp_path / "bg.jpg")
    with pytest.raises(ValueError, match="1-3 lines"):
        compose_cover(
            source=background,
            spec={"title": "한\n두\n세\n네"},
            index=1,
            total=8,
            output=tmp_path / "out.jpg",
        )


def test_cover_rejects_headline_that_cannot_shrink_to_fit(tmp_path: Path) -> None:
    background = _background(tmp_path / "bg.jpg")
    with pytest.raises(ValueError, match="does not fit"):
        compose_cover(
            source=background,
            spec={"title": "책 한 권 읽기 이 명령어 한 줄이면 정말로 전부 끝납니다 진짜로"},
            index=1,
            total=8,
            output=tmp_path / "out.jpg",
        )
