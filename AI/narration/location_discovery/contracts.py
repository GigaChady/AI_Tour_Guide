from __future__ import annotations

from typing import Protocol

from narration.location_discovery.geocoding_models import LocationAddress, NarrationDetailLevel


class GeocodingClient(Protocol):
    def reverse_geocode(
        self,
        lat: float,
        lon: float,
        language_tag: str = "en",
        zoom_level: NarrationDetailLevel = NarrationDetailLevel.DETAILED,
    ) -> LocationAddress: ...
