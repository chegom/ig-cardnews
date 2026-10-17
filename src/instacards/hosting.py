"""Upload rendered cards to publicly reachable HTTPS storage."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class HostingError(RuntimeError):
    pass


def _multipart(fields: dict[str, str], file_path: Path) -> tuple[bytes, str]:
    boundary = f"----instacards-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ])
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        file_path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def upload_cloudinary(path: Path) -> str:
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    folder = os.getenv("CLOUDINARY_FOLDER", "instacards").strip()
    if not all((cloud_name, api_key, api_secret)):
        raise HostingError("Cloudinary credentials are incomplete")
    timestamp = str(int(time.time()))
    params = {"folder": folder, "timestamp": timestamp}
    signature_source = "&".join(f"{key}={params[key]}" for key in sorted(params)) + api_secret
    signature = hashlib.sha1(signature_source.encode()).hexdigest()
    fields = {**params, "api_key": api_key, "signature": signature}
    body, content_type = _multipart(fields, path)
    request = urllib.request.Request(
        f"https://api.cloudinary.com/v1_1/{urllib.parse.quote(cloud_name)}/image/upload",
        data=body,
        method="POST",
        headers={"Content-Type": content_type, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise HostingError(f"Cloudinary upload failed: {error}") from error
    url = payload.get("secure_url")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise HostingError("Cloudinary did not return a secure_url")
    return url


def publish_static(path: Path) -> str:
    public_dir_text = os.getenv("MEDIA_PUBLIC_DIR", "").strip()
    base_url = os.getenv("MEDIA_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not public_dir_text or not base_url.startswith("https://"):
        raise HostingError("MEDIA_PUBLIC_DIR and an HTTPS MEDIA_PUBLIC_BASE_URL are required")
    public_dir = Path(public_dir_text).expanduser()
    public_dir.mkdir(parents=True, exist_ok=True)
    target = public_dir / path.name
    shutil.copy2(path, target)
    return f"{base_url}/{urllib.parse.quote(path.name)}"


def upload(path: Path) -> str:
    provider = os.getenv("MEDIA_HOST", "cloudinary").strip().lower()
    if provider == "cloudinary":
        return upload_cloudinary(path)
    if provider == "static":
        return publish_static(path)
    raise HostingError("MEDIA_HOST must be cloudinary or static")

