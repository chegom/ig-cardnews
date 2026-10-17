#!/usr/bin/env python3
"""Render carousel backgrounds with gpt-image-2 through the Codex CLI.

Mirrors scripts/render_flux_plan.py: it reads the same scene plan and writes
<slide_id>/1.jpg into the output directory, so backgrounds.json and the
compositor do not care which generator produced the photograph.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image

NO_TEXT = (
    " The final image itself contains absolutely no text, letters, numbers, logos, labels, "
    "captions, watermark, border, interface, or readable signage."
)


def generate(prompt: str, target: Path, repo: Path, quality: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    png = target.with_suffix(".png")
    instruction = (
        "Perform the following tasks:\n"
        "1. Use the built-in image_gen tool to generate an image.\n"
        f"2. Prompt: '{prompt}{NO_TEXT}'\n"
        "3. Size: 1024x1536\n"
        f"4. Quality: {quality}\n"
        "5. Count: 1\n"
        f"6. Copy the generated image to '{png}'.\n"
        "7. Print the saved file path."
    )
    command = [
        "codex", "exec", instruction,
        "-C", str(repo),
        "-s", "workspace-write",
        "-c", 'model_reasoning_effort="low"',
        "--skip-git-repo-check",
    ]
    print(f"START {target.parent.name}", flush=True)
    done = subprocess.run(command, text=True, capture_output=True, check=False)
    if not png.is_file():
        detail = (done.stderr or done.stdout).strip()[-400:]
        raise RuntimeError(f"gpt-image-2 failed for {target}: {detail}")
    with Image.open(png) as opened:
        opened.convert("RGB").save(target, "JPEG", quality=95, optimize=True)
    png.unlink()
    print(f"DONE  {target}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render backgrounds with gpt-image-2 via Codex")
    parser.add_argument("plan", type=Path, help="scene plan JSON: {\"scenes\": {slide_id: prompt}}")
    parser.add_argument("output", type=Path)
    parser.add_argument("--quality", default="high", choices=("low", "medium", "high", "auto"))
    parser.add_argument("--only")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    scenes = json.loads(args.plan.read_text(encoding="utf-8"))["scenes"]
    written = []
    for slide_id, prompt in scenes.items():
        if args.only and slide_id != args.only:
            continue
        target = args.output / slide_id / "1.jpg"
        generate(prompt, target, repo, args.quality)
        written.append({"slide_id": slide_id, "path": str(target)})
    manifest = args.output / "gpt-generation.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"items": written}, indent=2), encoding="utf-8")
    print(f"MANIFEST {manifest}", flush=True)


if __name__ == "__main__":
    main()
