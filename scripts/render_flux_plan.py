#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


FLUXCTL = os.environ.get("FLUXCTL_BIN", "fluxctl")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")


def render(prompt: str, seed: int, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    full_prompt = (
        f"{prompt} The final image itself contains absolutely no text, letters, numbers, "
        "logos, labels, captions, watermark, border, interface, or readable signage."
    )
    command = [
        FLUXCTL,
        "image",
        "--prompt",
        full_prompt,
        "--width",
        "1024",
        "--height",
        "1280",
        "--seed",
        str(seed),
        "--timeout",
        "1200",
        "--base-url",
        COMFYUI_URL,
        "--output",
        str(output),
    ]
    print(f"START {output.name} seed={seed}", flush=True)
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"FLUX failed for {output}: {detail}")
    print(f"DONE  {output}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render FLUX candidates from a visual plan")
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("covers", "slides"), required=True)
    parser.add_argument("--variants", type=int, default=2)
    parser.add_argument("--start-slide", type=int, default=2)
    parser.add_argument("--only-slide")
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    records = []
    if args.mode == "covers":
        jobs = [
            (item["candidate_id"], item["flux_prompt"], int(item["seed"]))
            for item in plan["cover_candidates"]
        ]
        for name, prompt, seed in jobs:
            output = args.output / f"{name}.jpg"
            render(prompt, seed, output)
            records.append({"candidate_id": name, "seed": seed, "path": str(output)})
    else:
        slides = plan["slides"][args.start_slide - 1 :]
        if args.only_slide:
            slides = [slide for slide in slides if slide["slide_id"] == args.only_slide]
        for slide in slides:
            base_seed = int(slide["seed"])
            for variant in range(1, args.variants + 1):
                seed = base_seed + (variant - 1) * 73
                name = f"{slide['slide_id']}-{variant}"
                output = args.output / slide["slide_id"] / f"{variant}.jpg"
                render(slide["flux_prompt"], seed, output)
                records.append(
                    {"slide_id": slide["slide_id"], "variant": variant, "seed": seed, "path": str(output)}
                )
    manifest = args.output / f"{args.mode}-generation.json"
    manifest.write_text(json.dumps({"items": records}, indent=2), encoding="utf-8")
    print(f"MANIFEST {manifest}", flush=True)


if __name__ == "__main__":
    main()
