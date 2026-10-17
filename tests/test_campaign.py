from __future__ import annotations

import json
from pathlib import Path

import pytest

from instacards.campaign import load_campaign


def test_load_campaign(tmp_path: Path) -> None:
    path = tmp_path / "campaign.json"
    path.write_text(
        json.dumps({
            "slug": "demo-cards",
            "caption": "hello",
            "hashtags": ["one", "#two"],
            "slides": [{"headline": "Title", "body": "Body", "prompt": "A scene"}],
        }),
        encoding="utf-8",
    )
    campaign = load_campaign(path)
    assert campaign.instagram_caption == "hello\n\n#one #two"
    assert campaign.slides[0].headline == "Title"


def test_rejects_more_than_ten_slides(tmp_path: Path) -> None:
    path = tmp_path / "campaign.json"
    path.write_text(
        json.dumps({
            "slug": "too-many",
            "slides": [{"headline": "T", "prompt": "P"}] * 11,
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="1-10"):
        load_campaign(path)

