"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from instacards.campaign import Campaign, load_campaign
from instacards.composer import compose_slide, make_draft_background
from instacards.flux import FluxError, render_background
from instacards.hosting import HostingError, upload
from instacards.instagram import InstagramClient, InstagramError


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _asset_dir(root: Path, campaign: Campaign, *, draft: bool) -> Path:
    return root / campaign.slug / ("draft" if draft else "production")


def render(campaign: Campaign, *, root: Path, draft: bool, force: bool) -> list[Path]:
    asset_dir = _asset_dir(root, campaign, draft=draft)
    backgrounds = asset_dir / "backgrounds"
    cards = asset_dir / "cards"
    outputs: list[Path] = []
    for index, slide in enumerate(campaign.slides, start=1):
        background = slide.background or backgrounds / f"{index:02d}.jpg"
        card = cards / f"{index:02d}.jpg"
        if slide.background and not background.is_file():
            raise FileNotFoundError(f"slide {index} background not found: {background}")
        if not slide.background and (force or not background.is_file()):
            if draft:
                make_draft_background(background, index)
                seed = slide.seed
            else:
                seed = render_background(
                    prompt=slide.prompt,
                    style_prompt=campaign.theme.style_prompt,
                    output=background,
                    seed=slide.seed,
                )
            print(f"[{index}/{len(campaign.slides)}] background ready (seed={seed})", file=sys.stderr)
        if force or not card.is_file() or card.stat().st_mtime < background.stat().st_mtime:
            compose_slide(
                background=background,
                slide=slide,
                campaign=campaign,
                index=index,
                output=card,
            )
        outputs.append(card)
        print(f"[{index}/{len(campaign.slides)}] card ready: {card}", file=sys.stderr)
    return outputs


def do_publish(campaign: Campaign, cards: list[Path]) -> dict:
    urls = []
    for index, card in enumerate(cards, start=1):
        url = upload(card)
        urls.append(url)
        print(f"[{index}/{len(cards)}] uploaded", file=sys.stderr)
    alt_texts = [slide.alt_text or slide.headline.replace("\n", " ") for slide in campaign.slides]
    result = InstagramClient().publish_images(
        urls=urls,
        alt_texts=alt_texts,
        caption=campaign.instagram_caption,
        ai_generated=campaign.ai_generated,
    )
    return {"media_id": result.media_id, "container_id": result.container_id, "urls": urls}


def cmd_doctor(_: argparse.Namespace) -> int:
    checks: dict[str, dict[str, object]] = {}
    base_url = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base_url}/system_stats", timeout=3) as response:
            checks["comfyui"] = {"ok": response.status == 200, "url": base_url}
    except (urllib.error.URLError, TimeoutError) as error:
        checks["comfyui"] = {"ok": False, "url": base_url, "error": str(error)}
    fluxctl = Path(os.getenv("FLUXCTL_BIN", "fluxctl")).expanduser()
    checks["fluxctl"] = {"ok": fluxctl.is_file(), "path": str(fluxctl)}
    checks["instagram"] = {
        "ok": bool(os.getenv("INSTAGRAM_USER_ID") and os.getenv("INSTAGRAM_ACCESS_TOKEN")),
        "user_id_set": bool(os.getenv("INSTAGRAM_USER_ID")),
        "access_token_set": bool(os.getenv("INSTAGRAM_ACCESS_TOKEN")),
    }
    host = os.getenv("MEDIA_HOST", "cloudinary")
    if host == "cloudinary":
        configured = all(os.getenv(key) for key in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"))
    else:
        configured = bool(os.getenv("MEDIA_PUBLIC_DIR") and os.getenv("MEDIA_PUBLIC_BASE_URL"))
    checks["media_host"] = {"ok": configured, "provider": host}
    _emit({"ok": all(item["ok"] for item in checks.values()), "checks": checks})
    return 0 if checks["comfyui"]["ok"] and checks["fluxctl"]["ok"] else 1


def cmd_render(args: argparse.Namespace) -> int:
    campaign = load_campaign(args.campaign)
    cards = render(campaign, root=args.output_dir, draft=args.draft, force=args.force)
    _emit({"ok": True, "campaign": campaign.slug, "cards": [str(path) for path in cards]})
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    campaign = load_campaign(args.campaign)
    cards = render(campaign, root=args.output_dir, draft=args.draft, force=args.force)
    payload: dict[str, object] = {"ok": True, "campaign": campaign.slug, "cards": [str(path) for path in cards], "published": False}
    if args.publish:
        if args.draft:
            raise ValueError("draft backgrounds cannot be published")
        payload.update(do_publish(campaign, cards))
        payload["published"] = True
    _emit(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="instacards", description="FLUX/ComfyUI Instagram card-news automation")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="check ComfyUI and publishing configuration")
    doctor.set_defaults(handler=cmd_doctor)
    render_parser = sub.add_parser("render", help="render cards without publishing")
    run_parser = sub.add_parser("run", help="render cards and optionally publish")
    for command in (render_parser, run_parser):
        command.add_argument("campaign", type=Path)
        command.add_argument("--output-dir", type=Path, default=Path("output"))
        command.add_argument("--draft", action="store_true", help="use quick synthetic backgrounds instead of FLUX")
        command.add_argument("--force", action="store_true", help="regenerate existing assets")
    render_parser.set_defaults(handler=cmd_render)
    run_parser.add_argument("--publish", action="store_true", help="upload and publish the carousel to Instagram")
    run_parser.set_defaults(handler=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (ValueError, OSError, FluxError, HostingError, InstagramError) as error:
        print(f"error: {error}", file=sys.stderr)
        _emit({"ok": False, "error": str(error), "type": type(error).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
