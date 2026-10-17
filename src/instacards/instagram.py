"""Instagram content publishing API client."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class InstagramError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishedPost:
    media_id: str
    container_id: str


class InstagramClient:
    def __init__(self, *, user_id: str | None = None, token: str | None = None, version: str | None = None) -> None:
        self.user_id = (user_id or os.getenv("INSTAGRAM_USER_ID", "")).strip()
        self.token = (token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")).strip()
        self.version = (version or os.getenv("INSTAGRAM_API_VERSION", "v26.0")).strip()
        if not self.user_id or not self.token:
            raise InstagramError("INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN are required")
        if not self.version.startswith("v"):
            raise InstagramError("INSTAGRAM_API_VERSION must look like v26.0")
        self.base = f"https://graph.instagram.com/{self.version}"

    def _request(self, method: str, path: str, fields: dict[str, str] | None = None) -> dict:
        params = dict(fields or {})
        params["access_token"] = self.token
        encoded = urllib.parse.urlencode(params).encode()
        url = f"{self.base}/{path.lstrip('/')}"
        if method == "GET":
            url = f"{url}?{encoded.decode()}"
            data = None
        else:
            data = encoded
        request = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", "replace")
            try:
                message = json.loads(raw).get("error", {}).get("message", raw)
            except json.JSONDecodeError:
                message = raw
            raise InstagramError(f"Instagram API {error.code}: {message}") from None
        except (urllib.error.URLError, json.JSONDecodeError) as error:
            raise InstagramError(f"Instagram API request failed: {error}") from error

    def create_image(self, *, image_url: str, alt_text: str = "", carousel_item: bool = False, caption: str = "", ai_generated: bool = False) -> str:
        fields = {"image_url": image_url}
        if alt_text:
            fields["alt_text"] = alt_text
        if carousel_item:
            fields["is_carousel_item"] = "true"
        if caption:
            fields["caption"] = caption
        if ai_generated:
            fields["is_ai_generated"] = "true"
        payload = self._request("POST", f"{self.user_id}/media", fields)
        if not payload.get("id"):
            raise InstagramError("image container response did not contain an id")
        return str(payload["id"])

    def create_carousel(self, *, children: list[str], caption: str, ai_generated: bool) -> str:
        if not 2 <= len(children) <= 10:
            raise InstagramError("a carousel requires 2-10 child containers")
        fields = {
            "media_type": "CAROUSEL",
            "children": json.dumps(children),
            "caption": caption,
        }
        if ai_generated:
            fields["is_ai_generated"] = "true"
        payload = self._request("POST", f"{self.user_id}/media", fields)
        if not payload.get("id"):
            raise InstagramError("carousel container response did not contain an id")
        return str(payload["id"])

    def wait_until_ready(self, container_id: str, *, timeout: int = 300) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            payload = self._request("GET", container_id, {"fields": "status_code"})
            status = payload.get("status_code")
            if status in {"FINISHED", "PUBLISHED"}:
                return
            if status in {"ERROR", "EXPIRED"}:
                raise InstagramError(f"container {container_id} entered status {status}")
            time.sleep(5)
        raise InstagramError(f"container {container_id} was not ready within {timeout}s")

    def publish(self, container_id: str) -> PublishedPost:
        self.wait_until_ready(container_id)
        payload = self._request("POST", f"{self.user_id}/media_publish", {"creation_id": container_id})
        media_id = payload.get("id")
        if not media_id:
            raise InstagramError("publish response did not contain a media id")
        return PublishedPost(media_id=str(media_id), container_id=container_id)

    def publish_images(self, *, urls: list[str], alt_texts: list[str], caption: str, ai_generated: bool) -> PublishedPost:
        if len(urls) != len(alt_texts):
            raise InstagramError("URL and alt-text counts differ")
        if len(urls) == 1:
            container = self.create_image(
                image_url=urls[0], alt_text=alt_texts[0], caption=caption, ai_generated=ai_generated
            )
            return self.publish(container)
        children: list[str] = []
        for url, alt_text in zip(urls, alt_texts, strict=True):
            child = self.create_image(image_url=url, alt_text=alt_text, carousel_item=True)
            self.wait_until_ready(child)
            children.append(child)
        carousel = self.create_carousel(children=children, caption=caption, ai_generated=ai_generated)
        return self.publish(carousel)

