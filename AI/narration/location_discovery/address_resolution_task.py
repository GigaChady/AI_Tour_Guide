from __future__ import annotations

from narration.location_discovery.contracts import GeocodingClient
from narration.schemas import LocationAddress, NarrationDetailLevel


class AddressResolutionTask:
    def __init__(
        self,
        geocoding_client: GeocodingClient,
    ):
        self.geocoding_client = geocoding_client

    def run(
        self,
        lat: float,
        lon: float,
        language_tag: str = "en",
        zoom_level: NarrationDetailLevel = NarrationDetailLevel.DETAILED,
    ) -> LocationAddress:
        return self.geocoding_client.reverse_geocode(
            lat=lat,
            lon=lon,
            language_tag=language_tag,
            zoom_level=zoom_level,
        )
