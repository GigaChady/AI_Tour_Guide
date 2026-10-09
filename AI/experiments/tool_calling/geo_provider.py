from __future__ import annotations

from typing import Protocol

from experiments.tool_calling.contracts import Coordinates, LocationContext


class GeoProvider(Protocol):
    def reverse_geocode(self, lat: float, lon: float) -> LocationContext: ...

    def geocode_place(
        self,
        place_name: str,
        city: str,
        country: str,
    ) -> Coordinates | None: ...


class NominatimGeoProvider:
    def __init__(self):
        from integrations.geocoding.nominatim.nominatim_client import NominatimClient

        self.client = NominatimClient()

    def reverse_geocode(self, lat: float, lon: float) -> LocationContext:
        location = self.client.reverse_geocode(lat=lat, lon=lon, language_tag="pl")
        address = location.raw.get("address", {})
        return LocationContext(
            lat=lat,
            lon=lon,
            street=(
                address.get("road")
                or address.get("pedestrian")
                or address.get("footway")
                or ""
            ),
            neighbourhood=address.get("neighbourhood") or address.get("suburb") or "",
            district=address.get("city_district") or address.get("county") or "",
            city=(
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("municipality")
                or ""
            ),
            country=address.get("country") or "",
        )

    def geocode_place(
        self,
        place_name: str,
        city: str,
        country: str,
    ) -> Coordinates | None:
        query = ", ".join(part for part in [place_name, city, country] if part)
        result = self.client.geolocator.geocode(
            query,
            language="pl",
            timeout=self.client.config.timeout_seconds,
        )
        if result is None:
            return None
        return Coordinates(
            lat=float(result.latitude),
            lon=float(result.longitude),
            display_name=str(result.address),
        )


class MockGeoProvider:
    _PLACES = {
        "dworzec wrocław nadodrze": Coordinates(
            51.1234,
            17.0332,
            "Dworzec Wrocław Nadodrze, Wrocław, Polska",
        ),
    }

    def reverse_geocode(self, lat: float, lon: float) -> LocationContext:
        return LocationContext(
            lat=lat,
            lon=lon,
            street="Jedności Narodowej",
            neighbourhood="Nadodrze",
            district="Śródmieście",
            city="Wrocław",
            country="Polska",
        )

    def geocode_place(
        self,
        place_name: str,
        city: str,
        country: str,
    ) -> Coordinates | None:
        return self._PLACES.get(place_name.casefold().strip())
