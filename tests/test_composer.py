from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from instacards.campaign import load_campaign
from instacards.composer import CANVAS, compose_slide, make_draft_background


def _demo_campaign(tmp_path: Path):
    campaign_path = tmp_path / "campaign.json"
    campaign_path.write_text(
        json.dumps({
            "slug": "demo-cards",
            "theme": {"brand": "TEST"},
            "slides": [{"headline": "한글 제목", "body": "짧은 본문입니다.", "prompt": "P"}],
        }),
        encoding="utf-8",
    )
    return load_campaign(campaign_path)


def test_compose_jpeg(tmp_path: Path) -> None:
    campaign = _demo_campaign(tmp_path)
    background = tmp_path / "background.jpg"
    output = tmp_path / "card.jpg"
    make_draft_background(background, 1)
    compose_slide(background=background, slide=campaign.slides[0], campaign=campaign, index=1, output=output)
    with Image.open(output) as image:
        assert image.size == CANVAS
        assert image.format == "JPEG"


def test_compose_writes_layout_manifest(tmp_path: Path) -> None:
    campaign = _demo_campaign(tmp_path)
    background = tmp_path / "background.jpg"
    output = tmp_path / "card.jpg"
    manifest_path = tmp_path / "card.layout.json"
    make_draft_background(background, 1)

    compose_slide(
        background=background,
        slide=campaign.slides[0],
        campaign=campaign,
        index=1,
        output=output,
        manifest=manifest_path,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["slide"] == 1
    assert manifest["canvas"] == list(CANVAS)
    assert len(manifest["safe_area"]) == 4
    roles = {element["role"] for element in manifest["elements"]}
    assert {"title", "body", "brand", "page"} <= roles
    title = next(element for element in manifest["elements"] if element["role"] == "title")
    assert title["color"] == "#FFFFFF"
    assert len(title["bg_rgb"]) == 3
    assert len(title["bbox"]) == 4
    body = next(element for element in manifest["elements"] if element["role"] == "body")
    assert body["lines"] >= 1

