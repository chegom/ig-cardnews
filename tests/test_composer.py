from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from instacards.campaign import load_campaign
from instacards.composer import CANVAS, compose_slide, make_draft_background


def test_compose_jpeg(tmp_path: Path) -> None:
    campaign_path = tmp_path / "campaign.json"
    campaign_path.write_text(
        json.dumps({
            "slug": "demo-cards",
            "theme": {"brand": "TEST"},
            "slides": [{"headline": "한글 제목", "body": "짧은 본문입니다.", "prompt": "P"}],
        }),
        encoding="utf-8",
    )
    campaign = load_campaign(campaign_path)
    background = tmp_path / "background.jpg"
    output = tmp_path / "card.jpg"
    make_draft_background(background, 1)
    compose_slide(background=background, slide=campaign.slides[0], campaign=campaign, index=1, output=output)
    with Image.open(output) as image:
        assert image.size == CANVAS
        assert image.format == "JPEG"

