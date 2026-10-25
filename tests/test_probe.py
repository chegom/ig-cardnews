import json
from pathlib import Path

import pytest
from PIL import Image

from instacards.audit import AuditRules, audit_directory
from instacards.editorial import CANVAS
from instacards.probe import compose_probe_carousel


def _render_probe_deck(tmp_path: Path, color=(120, 110, 100)) -> Path:
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    for name in ("01.jpg", "02.jpg", "06.jpg"):
        Image.new("RGB", CANVAS, color).save(backgrounds / name)
    spec = tmp_path / "probe.json"
    spec.write_text(json.dumps(_probe_payload(), ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "cards"
    compose_probe_carousel(spec, backgrounds, output)
    return output


def test_probe_writes_layout_manifest_per_card(tmp_path: Path) -> None:
    output = _render_probe_deck(tmp_path)

    manifests = sorted(p.name for p in output.glob("*.layout.json"))
    assert manifests == ["01.layout.json", "02.layout.json", "06.layout.json"]
    first = json.loads((output / "01.layout.json").read_text(encoding="utf-8"))
    assert first["canvas"] == list(CANVAS)
    assert "title" in {e["role"] for e in first["elements"]}


def test_probe_audit_passes_on_dark_gradient_deck(tmp_path: Path) -> None:
    output = _render_probe_deck(tmp_path)

    assert audit_directory(output).worst_level != "red"


def test_probe_audit_flags_red_under_strict_contrast(tmp_path: Path) -> None:
    output = _render_probe_deck(tmp_path)

    report = audit_directory(output, AuditRules(min_contrast_large=25.0, min_contrast_body=25.0))

    assert report.ok is False


def _probe_payload() -> dict:
    return {
        "slides": [
            {
                "slide_id": "s01",
                "role": "cover",
                "kicker": "한파 전 저장",
                "title": "한파 대비,\n하루 체크",
                "body": "출근길부터 집 안까지",
                "actions": [],
            },
            {
                "slide_id": "s02",
                "role": "general_info",
                "layout": "bottom_story",
                "kicker": "07:00 · 외출 전",
                "title": "체감온도,\n먼저 봐요",
                "body": "추운 날은 바깥 활동을 줄이고\n가족도 함께 살펴요.",
                "actions": ["어르신·어린이는 더 세심히", "만성질환자는 무리하지 않기"],
            },
            {
                "slide_id": "s06",
                "role": "emergency_alert",
                "layout": "center_alert",
                "kicker": "위험 신호",
                "title": "심한 떨림\n어눌한 말\n의식 저하",
                "body": "의심되면 119에 도움을 요청하세요.",
                "actions": ["따뜻한 곳으로", "젖은 옷 벗기고 담요로", "의식 흐리면 먹이지 않기"],
            },
        ]
    }


def test_probe_renders_every_role_as_a_full_bleed_photo_card(tmp_path: Path) -> None:
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    source_colors = {
        "01.jpg": (170, 115, 70),
        "02.jpg": (70, 130, 175),
        "06.jpg": (120, 95, 150),
    }
    for name, color in source_colors.items():
        Image.new("RGB", CANVAS, color).save(backgrounds / name)
    spec = tmp_path / "probe.json"
    spec.write_text(json.dumps(_probe_payload(), ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "cards"

    compose_probe_carousel(spec, backgrounds, output)

    assert sorted(path.name for path in output.glob("*.jpg")) == ["01.jpg", "02.jpg", "06.jpg"]
    for name in ("01.jpg", "02.jpg", "06.jpg"):
        with Image.open(output / name) as image:
            assert image.size == CANVAS
            assert image.mode == "RGB"
    for name, color in source_colors.items():
        with Image.open(output / name) as card:
            top_photo = card.getpixel((540, 180))
            assert max(abs(top_photo[channel] - color[channel]) for channel in range(3)) < 28
            lower_overlay = card.getpixel((540, 1240))
            assert sum(lower_overlay) < sum(color)


def test_probe_rejects_unknown_role(tmp_path: Path) -> None:
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    spec = tmp_path / "probe.json"
    spec.write_text(
        json.dumps({"slides": [{"slide_id": "s02", "role": "collage", "title": "제목"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown probe role"):
        compose_probe_carousel(spec, backgrounds, tmp_path / "cards")


def test_probe_requires_source_for_every_photo_role(tmp_path: Path) -> None:
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    spec = tmp_path / "probe.json"
    spec.write_text(
        json.dumps(
            {
                "slides": [
                    {
                        "slide_id": "s02",
                        "role": "general_info",
                        "title": "체감온도 먼저",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="02.jpg"):
        compose_probe_carousel(spec, backgrounds, tmp_path / "cards")


def test_cover_page_marker_stays_visible_on_dark_photo(tmp_path: Path) -> None:
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    Image.new("RGB", CANVAS, (0, 0, 0)).save(backgrounds / "01.jpg")
    payload = _probe_payload()
    payload["slides"] = [payload["slides"][0]]
    spec = tmp_path / "probe.json"
    spec.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    compose_probe_carousel(spec, backgrounds, tmp_path / "cards")

    with Image.open(tmp_path / "cards" / "01.jpg") as image:
        marker = image.crop((900, 56, 1012, 112)).convert("L")
        assert max(marker.get_flattened_data()) >= 220


def test_bottom_story_uses_the_lower_reading_area_for_copy(tmp_path: Path) -> None:
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    Image.new("RGB", CANVAS, (246, 246, 246)).save(backgrounds / "02.jpg")
    payload = _probe_payload()
    payload["slides"] = [payload["slides"][1]]
    spec = tmp_path / "probe.json"
    spec.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    compose_probe_carousel(spec, backgrounds, tmp_path / "cards")

    with Image.open(tmp_path / "cards" / "02.jpg") as image:
        lower_copy = image.crop((60, 840, 1020, 1260)).convert("RGB")
        dark_pixels = sum(
            1
            for pixel in lower_copy.get_flattened_data()
            if max(pixel) < 80
        )
        assert dark_pixels >= 1200
