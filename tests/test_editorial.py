import json
from pathlib import Path

from PIL import Image

from instacards.editorial import CANVAS, compose_editorial_carousel


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
