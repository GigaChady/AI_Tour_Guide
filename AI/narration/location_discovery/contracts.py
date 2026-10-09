from __future__ import annotations

from typing import Any, Protocol

from narration.schemas import LocationAddress, NarrationDetailLevel, PoiCandidate


class GeocodingClient(Protocol):
    def reverse_geocode(
        self,
        lat: float,
        lon: float,
        language_tag: str = "en",
        zoom_level: NarrationDetailLevel = NarrationDetailLevel.DETAILED,
    ) -> LocationAddress: ...


class PoiDataClient(Protocol):
    def get_nearby_poi_data(
        self,
        lat: float,
        lon: float,
        radius: int = 50,
    ) -> Any | None: ...


class PoiParser(Protocol):
    def parse(self, data: Any) -> list[PoiCandidate]: ...
