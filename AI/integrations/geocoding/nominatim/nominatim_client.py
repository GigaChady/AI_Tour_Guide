from __future__ import annotations

import logging
import time
from threading import RLock

from integrations.geocoding.nominatim.config import NominatimConfig
from narration.knowledge import GeocodedPlace
from narration.location_discovery.geocoding_models import LocationAddress, NarrationDetailLevel

logger = logging.getLogger(__name__)


class NominatimClient:
    _request_lock = RLock()
    _last_request_at = 0.0

    def __init__(
        self,
        config: NominatimConfig | None = None,
        user_agent: str | None = None,
        geolocator=None,
        min_interval_seconds: float = 1.0,
    ):
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be nonnegative")

        self.config = config or NominatimConfig()
        if geolocator is None:
            from geopy.geocoders import Nominatim

            geolocator = Nominatim(user_agent=user_agent or self.config.user_agent)
        self.geolocator = geolocator
        self.min_interval_seconds = min_interval_seconds

    def _before_request(self) -> None:
        with self._request_lock:
            wait = self.min_interval_seconds - (time.monotonic() - type(self)._last_request_at)
            if wait > 0:
                time.sleep(wait)
            type(self)._last_request_at = time.monotonic()

    def reverse_geocode(
        self,
        lat: float,
        lon: float,
        language_tag: str = "en",
        zoom_level: NarrationDetailLevel = NarrationDetailLevel.DETAILED,
    ) -> LocationAddress:
        try:
            self._before_request()
            location = self.geolocator.reverse(
                f"{lat}, {lon}",
                language=language_tag,
                zoom=zoom_level.value,
                timeout=self.config.timeout_seconds,
            )
            return LocationAddress(raw=location.raw if location else {})
        except Exception as e:
            logger.warning("Could not reverse geocode location: %s", e)
            return LocationAddress()

    def search_place(
        self, name: str, *, city: str, country: str = "", limit: int = 5
    ) -> list[GeocodedPlace]:
        if not name.strip() or not city.strip() or not 1 <= limit <= 5:
            raise ValueError("name, city and limit (1-5) are required")
        query = ", ".join(part for part in (name, city, country) if part)
        self._before_request()
        found = self.geolocator.geocode(
            query,
            exactly_one=False,
            limit=limit,
            addressdetails=True,
            namedetails=True,
            language="pl",
            timeout=self.config.timeout_seconds,
        )
        if found is None:
            return []
        locations = found if isinstance(found, (list, tuple)) else [found]
        results: list[GeocodedPlace] = []
        for location in locations:
            raw = location.raw or {}
            osm_type, osm_id = raw.get("osm_type"), raw.get("osm_id")
            if not osm_type or not osm_id:
                continue
            address = raw.get("address") or {}
            names = raw.get("namedetails") or {}
            display_name = str(raw.get("display_name") or location.address or "")
            result_city = next(
                (str(address[key]) for key in ("city", "town", "village", "municipality")
                 if address.get(key)),
                "",
            )
            if not result_city and city.casefold() in display_name.casefold():
                result_city = city
            aliases = [
                part.strip() for value in names.values() if isinstance(value, str)
                for part in value.split(";") if part.strip()
            ]
            results.append(GeocodedPlace(
                name=str(raw.get("name") or names.get("name") or display_name.split(",")[0]),
                lat=location.latitude,
                lon=location.longitude,
                coordinate_source=f"nominatim:{osm_type}:{osm_id}",
                city=result_city,
                country=str(address.get("country") or ""),
                street=str(address.get("road") or address.get("pedestrian") or ""),
                district=str(address.get("neighbourhood") or address.get("suburb")
                             or address.get("city_district") or ""),
                aliases=aliases,
                external_ids={"osm": f"{osm_type}:{osm_id}"},
            ))
        return results
