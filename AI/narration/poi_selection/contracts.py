from __future__ import annotations

from typing import Protocol


class SeenPoiRepository(Protocol):
    def get_seen(self, session_id: str) -> set[str]: ...

    def mark_seen(self, session_id: str, poi_name: str) -> None: ...
