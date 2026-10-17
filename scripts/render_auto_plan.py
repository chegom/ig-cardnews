#!/usr/bin/env python3
"""Render carousel backgrounds with gpt-image-2, or locally with FLUX.

gpt-image-2 is the default because it only needs the Codex CLI and a ChatGPT
login.  FLUX runs free on your own GPU but needs ComfyUI serving a FLUX model,
so it is opt-in via --engine flux (see FLUXCTL_BIN / COMFYUI_URL below).

What separates the two is not sharpness but prompt adherence: FLUX will happily
render a bright forest when the brief asked for a misty valley, and a pixel
metric cannot see that.  So each scene carries a `must_have` checklist, the
rendered frames are reviewed against it, and only the failures are re-rendered
on the other engine.

    render_auto_plan.py plan.json out/                     # gpt-image-2
    render_auto_plan.py plan.json out/ --engine flux       # free, local
    review out/qc/contact-sheet.jpg + out/qc/checklist.json
    render_auto_plan.py plan.json out/ --escalate s04      # redo one scene on gpt
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
FLUXCTL_BIN = os.environ.get("FLUXCTL_BIN", "fluxctl")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
sys.path.insert(0, str(REPO / "src"))
from instacards.editorial import BOLD_FONT  # noqa: E402

NO_TEXT = (
    " The final image itself contains absolutely no text, letters, numbers, logos, labels, "
    "captions, watermark, border, interface, or readable signage. 4:5 vertical."
)


def _flux(prompt: str, seed: int, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FLUXCTL_BIN, "image",
        "--prompt", prompt + NO_TEXT,
        "--width", "1024", "--height", "1280",
        "--seed", str(seed), "--timeout", "1200",
        "--base-url", COMFYUI_URL,
        "--output", str(target),
    ]
    done = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if done.returncode != 0:
        raise RuntimeError(
            f"FLUX failed for {target}: {(done.stderr or done.stdout).strip()[-300:]}\n"
            f"Set FLUXCTL_BIN and COMFYUI_URL, or drop --engine flux to use gpt-image-2."
        )


def _gpt(prompt: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    png = target.with_suffix(".png")
    instruction = (
        "Perform the following tasks:\n"
        "1. Use the built-in image_gen tool to generate an image.\n"
        f"2. Prompt: '{prompt}{NO_TEXT}'\n"
        "3. Size: 1024x1536\n4. Quality: high\n5. Count: 1\n"
        f"6. Copy the generated image to '{png}'.\n7. Print the saved file path."
    )
    subprocess.run(
        ["codex", "exec", instruction, "-C", str(REPO), "-s", "workspace-write",
         "-c", 'model_reasoning_effort="low"', "--skip-git-repo-check"],
        text=True, capture_output=True, check=False,
    )
    if not png.is_file():
        raise RuntimeError(f"gpt-image-2 failed for {target}")
    with Image.open(png) as opened:
        opened.convert("RGB").save(target, "JPEG", quality=95, optimize=True)
    png.unlink()


def _qc(output: Path, scenes: dict, engines: dict) -> None:
    qc = output / "qc"
    qc.mkdir(parents=True, exist_ok=True)
    ids = sorted(scenes)
    cols, cell = 4, 250
    rows = (len(ids) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell + 20, rows * (cell + 56) + 20), (244, 244, 247))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(BOLD_FONT), 22)
    for i, sid in enumerate(ids):
        path = output / sid / "1.jpg"
        if not path.is_file():
            continue
        with Image.open(path) as im:
            thumb = im.resize((cell - 20, round((cell - 20) * 1.25)), Image.Resampling.LANCZOS)
        x = 10 + (i % cols) * cell
        y = 10 + (i // cols) * (cell + 56)
        sheet.paste(thumb, (x, y))
        draw.text((x, y + thumb.height + 8), f"{sid}  [{engines[sid]}]", font=font, fill=(20, 22, 28))
    sheet.save(qc / "contact-sheet.jpg", quality=93)

    checklist = {
        sid: {"engine": engines[sid], "must_have": scenes[sid].get("must_have", []), "verdict": None}
        for sid in ids
    }
    (qc / "checklist.json").write_text(json.dumps(checklist, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"QC  {qc/'contact-sheet.jpg'}")
    print(f"QC  {qc/'checklist.json'}  — must_have 대조 후 실패분을 --escalate 로 재생성")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render carousel backgrounds (gpt-image-2 by default, FLUX optional)")
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--engine", choices=("gpt", "flux"), default="gpt",
                        help="기본 생성기 (기본값 gpt-image-2; flux는 로컬 ComfyUI 필요)")
    parser.add_argument("--escalate", default="", help="다른 엔진으로 다시 뽑을 slide_id (쉼표 구분)")
    args = parser.parse_args()

    scenes = json.loads(args.plan.read_text(encoding="utf-8"))["scenes"]
    escalate = {s.strip() for s in args.escalate.split(",") if s.strip()}
    engines: dict[str, str] = {}

    for sid, item in scenes.items():
        prompt = item["prompt"] if isinstance(item, dict) else item
        forced = item.get("engine") if isinstance(item, dict) else None
        seed = item.get("seed", 12345) if isinstance(item, dict) else 12345
        target = args.output / sid / "1.jpg"

        other = "flux" if args.engine == "gpt" else "gpt"
        engine = forced or (other if sid in escalate else args.engine)

        if escalate and sid not in escalate and forced is None:
            engines[sid] = f"{args.engine} (유지)"   # 재생성 단계에서는 나머지를 건드리지 않는다
            continue

        print(f"{engine.upper():5s} {sid}", flush=True)
        if engine == "gpt":
            _gpt(prompt, target)
            engines[sid] = "gpt-image-2"
        else:
            _flux(prompt, seed, target)
            engines[sid] = "flux"

    _qc(args.output, {k: (v if isinstance(v, dict) else {}) for k, v in scenes.items()}, engines)


if __name__ == "__main__":
    main()
