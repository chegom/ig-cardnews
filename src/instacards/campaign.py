"""Campaign input model and validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class Theme:
    accent: str = "#D7FF3F"
    text: str = "#FFFFFF"
    brand: str = ""
    style_prompt: str = (
        "editorial campaign photography, cinematic lighting, intentional negative "
        "space for Korean typography, cohesive visual system"
    )


@dataclass(frozen=True)
class Slide:
    headline: str
    body: str
    prompt: str
    eyebrow: str = ""
    alt_text: str = ""
    seed: int | None = None
    background: Path | None = None


@dataclass(frozen=True)
class Campaign:
    slug: str
    caption: str
    hashtags: tuple[str, ...]
    slides: tuple[Slide, ...]
    theme: Theme = field(default_factory=Theme)
    ai_generated: bool = True

    @property
    def instagram_caption(self) -> str:
        tags = " ".join(tag if tag.startswith("#") else f"#{tag}" for tag in self.hashtags)
        return "\n\n".join(part for part in (self.caption.strip(), tags.strip()) if part)


def _required_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any, path: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
    return value.strip()


def load_campaign(path: Path) -> Campaign:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid campaign JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError("campaign root must be an object")

    slug = _required_string(raw.get("slug"), "slug")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", slug):
        raise ValueError("slug must contain 2-64 lowercase letters, numbers, or hyphens")

    theme_raw = raw.get("theme") or {}
    if not isinstance(theme_raw, dict):
        raise ValueError("theme must be an object")
    accent = str(theme_raw.get("accent", "#D7FF3F"))
    text = str(theme_raw.get("text", "#FFFFFF"))
    if not HEX_COLOR.fullmatch(accent) or not HEX_COLOR.fullmatch(text):
        raise ValueError("theme accent/text must use #RRGGBB")
    theme = Theme(
        accent=accent,
        text=text,
        brand=_optional_string(theme_raw.get("brand"), "theme.brand"),
        style_prompt=_optional_string(theme_raw.get("style_prompt"), "theme.style_prompt")
        or Theme.style_prompt,
    )

    slides_raw = raw.get("slides")
    if not isinstance(slides_raw, list) or not 1 <= len(slides_raw) <= 10:
        raise ValueError("slides must contain 1-10 items")
    slides: list[Slide] = []
    for index, item in enumerate(slides_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"slides[{index}] must be an object")
        background = item.get("background")
        background_path = None
        if background:
            candidate = Path(str(background)).expanduser()
            background_path = candidate if candidate.is_absolute() else path.parent / candidate
        seed = item.get("seed")
        if seed is not None and not isinstance(seed, int):
            raise ValueError(f"slides[{index}].seed must be an integer")
        slides.append(
            Slide(
                headline=_required_string(item.get("headline"), f"slides[{index}].headline"),
                body=_optional_string(item.get("body"), f"slides[{index}].body"),
                prompt=_required_string(item.get("prompt"), f"slides[{index}].prompt"),
                eyebrow=_optional_string(item.get("eyebrow"), f"slides[{index}].eyebrow"),
                alt_text=_optional_string(item.get("alt_text"), f"slides[{index}].alt_text"),
                seed=seed,
                background=background_path,
            )
        )

    hashtags = raw.get("hashtags") or []
    if not isinstance(hashtags, list) or any(not isinstance(tag, str) for tag in hashtags):
        raise ValueError("hashtags must be an array of strings")
    campaign = Campaign(
        slug=slug,
        caption=_optional_string(raw.get("caption"), "caption"),
        hashtags=tuple(tag.strip() for tag in hashtags if tag.strip()),
        slides=tuple(slides),
        theme=theme,
        ai_generated=bool(raw.get("ai_generated", True)),
    )
    if len(campaign.instagram_caption) > 2200:
        raise ValueError("Instagram caption must not exceed 2200 characters")
    return campaign

