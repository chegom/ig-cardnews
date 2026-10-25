import json
from pathlib import Path

from PIL import Image

from instacards.audit import AuditRules, audit_directory
from instacards.editorial import CANVAS, compose_editorial_carousel


def _render_editorial_deck(tmp_path: Path) -> Path:
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    layouts = ["cover", "split", "photo_memo", "steps", "alert", "checklist"]
    slides = []
    for index, layout in enumerate(layouts, start=1):
        Image.new("RGB", CANVAS, (30 * index, 80, 120)).save(backgrounds / f"{index:02d}.jpg")
        slides.append({
            "layout": layout,
            "kicker": "겨울 안전",
            "title": "한파를 이기는 작은 준비",
            "body": "추위가 오기 전에 오늘 미리 점검하세요.",
            "bullets": ["겹쳐 입기", "수도관 보온", "위험 신호 확인"],
        })
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"slides": slides}, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "cards"
    compose_editorial_carousel(spec, backgrounds, output)
    return output


def test_editorial_writes_layout_manifest_per_card(tmp_path: Path) -> None:
    output = _render_editorial_deck(tmp_path)

    manifests = sorted(p.name for p in output.glob("*.layout.json"))
    assert manifests == [f"{i:02d}.layout.json" for i in range(1, 7)]
    first = json.loads((output / "01.layout.json").read_text(encoding="utf-8"))
    assert first["canvas"] == list(CANVAS)
    assert any(e["role"] == "text" for e in first["elements"])


def test_editorial_audit_passes_on_default_decks(tmp_path: Path) -> None:
    output = _render_editorial_deck(tmp_path)

    assert audit_directory(output).worst_level != "red"


def test_editorial_audit_flags_red_under_strict_contrast(tmp_path: Path) -> None:
    output = _render_editorial_deck(tmp_path)

    report = audit_directory(output, AuditRules(min_contrast_large=25.0, min_contrast_body=25.0))

    assert report.ok is False


def test_editorial_carousel_renders_all_layouts(tmp_path: Path) -> None:
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    layouts = ["cover", "split", "photo_memo", "steps", "alert", "checklist"]
    slides = []
    for index, layout in enumerate(layouts, start=1):
        Image.new("RGB", CANVAS, (30 * index, 80, 120)).save(backgrounds / f"{index:02d}.jpg")
        slides.append(
            {
                "layout": layout,
                "kicker": "겨울 안전",
                "title": "한파를 이기는 작은 준비",
                "body": "추위가 오기 전에 오늘 미리 점검하세요.",
                "bullets": ["겹쳐 입기", "수도관 보온", "위험 신호 확인"],
            }
        )
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"slides": slides}, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "cards"

    compose_editorial_carousel(spec, backgrounds, output)

    assert sorted(path.name for path in output.glob("*.jpg")) == [
        "01.jpg",
        "02.jpg",
        "03.jpg",
        "04.jpg",
        "05.jpg",
        "06.jpg",
    ]
    with Image.open(output / "01.jpg") as image:
        assert image.size == CANVAS
