from __future__ import annotations

from typing import Any, Protocol


class ImageStorage(Protocol):
    def upload_bytes(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "image/jpeg",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        ...


class PhotoGenerator(Protocol):
    def generate(self, image_type: str, count: int) -> str | None:
        ...
