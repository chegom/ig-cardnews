from __future__ import annotations

from instacards.instagram import InstagramClient


class FakeInstagramClient(InstagramClient):
    def __init__(self) -> None:
        super().__init__(user_id="123", token="secret", version="v26.0")
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        self.next_id = 0

    def _request(self, method: str, path: str, fields: dict[str, str] | None = None) -> dict:
        actual = dict(fields or {})
        self.calls.append((method, path, actual))
        if method == "GET":
            return {"status_code": "FINISHED"}
        self.next_id += 1
        return {"id": f"id-{self.next_id}"}


def test_carousel_publish_sequence() -> None:
    client = FakeInstagramClient()
    result = client.publish_images(
        urls=["https://cdn.test/1.jpg", "https://cdn.test/2.jpg"],
        alt_texts=["first", "second"],
        caption="caption",
        ai_generated=True,
    )
    post_calls = [call for call in client.calls if call[0] == "POST"]
    assert post_calls[0][2]["is_carousel_item"] == "true"
    assert post_calls[1][2]["is_carousel_item"] == "true"
    assert post_calls[2][2]["media_type"] == "CAROUSEL"
    assert post_calls[2][2]["is_ai_generated"] == "true"
    assert post_calls[-1][1] == "123/media_publish"
    assert result.media_id == "id-4"

