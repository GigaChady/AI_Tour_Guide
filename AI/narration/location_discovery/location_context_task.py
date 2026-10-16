from __future__ import annotations

from narration.knowledge import LocationContext
from narration.location_discovery.contracts import GeocodingClient
from narration.location_discovery.geocoding_models import NarrationDetailLevel


def _first(address: dict, *keys: str) -> str:
    return next((str(address[key]).strip() for key in keys if address.get(key)), "")


class LocationContextTask:
    """Convert the existing reverse-geocoding result into research context."""

    def __init__(self, geocoding_client: GeocodingClient):
        self.geocoding_client = geocoding_client

    def run(self, lat: float, lon: float, language_tag: str = "pl") -> LocationContext:
        # Validate before sending coordinates to an external provider.
        coordinates = LocationContext(lat=lat, lon=lon)
        result = self.geocoding_client.reverse_geocode(
            lat=coordinates.lat,
            lon=coordinates.lon,
            language_tag=language_tag,
            zoom_level=NarrationDetailLevel.DETAILED,
        )
        raw = result.raw if result is not None else {}
        address = raw.get("address") or {}
        return LocationContext(
            lat=coordinates.lat,
            lon=coordinates.lon,
            street=_first(address, "road", "pedestrian", "footway", "residential"),
            neighbourhood=_first(address, "neighbourhood", "quarter", "suburb"),
            district=_first(address, "city_district", "borough"),
            city=_first(address, "city", "town", "village", "municipality"),
            region=_first(address, "state", "region", "province"),
            country=_first(address, "country"),
        )
