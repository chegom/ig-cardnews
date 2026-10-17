"""Adapter for the already-installed fluxctl/ComfyUI workflow."""

from __future__ import annotations

import json
import os
import random
import subprocess
from pathlib import Path


DEFAULT_FLUXCTL = "fluxctl"
TEXT_FREE_SUFFIX = (
    " The image itself must contain no text, no letters, no numbers, no logo, "
    "no watermark, no UI, and no border. Reserve calm negative space in the upper-left "
    "and lower-left for typography that will be added later."
)


class FluxError(RuntimeError):
    pass


def render_background(
    *,
    prompt: str,
    style_prompt: str,
    output: Path,
    seed: int | None,
    base_url: str | None = None,
    fluxctl_bin: str | None = None,
    timeout: int = 900,
) -> int:
    binary = Path(fluxctl_bin or os.getenv("FLUXCTL_BIN", DEFAULT_FLUXCTL)).expanduser()
    if not binary.is_file():
        raise FluxError(f"fluxctl not found: {binary}")
    actual_seed = seed if seed is not None else random.randrange(0, 2**63)
    complete_prompt = ". ".join(part.strip(" .") for part in (prompt, style_prompt) if part.strip())
    complete_prompt += TEXT_FREE_SUFFIX
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(binary),
        "image",
        "--prompt",
        complete_prompt,
        "--width",
        "1024",
        "--height",
        "1280",
        "--seed",
        str(actual_seed),
        "--timeout",
        str(timeout),
        "--base-url",
        base_url or os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188"),
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise FluxError(detail)
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as error:
        raise FluxError("fluxctl returned an unreadable response") from error
    if not payload.get("ok") or not output.is_file():
        raise FluxError(str(payload.get("error") or "FLUX output was not created"))
    return int(payload.get("seed", actual_seed))

