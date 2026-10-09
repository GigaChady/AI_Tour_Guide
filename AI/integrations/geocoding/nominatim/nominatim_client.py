from __future__ import annotations

import logging

from integrations.geocoding.nominatim.config import NominatimConfig
from narration.schemas import LocationAddress, NarrationDetailLevel

logger = logging.getLogger(__name__)


class NominatimClient:
    def __init__(
        self,
        config: NominatimConfig | None = None,
        user_agent: str | None = None,
    ):
        from geopy.geocoders import Nominatim

        self.config = config or NominatimConfig()
        self.geolocator = Nominatim(user_agent=user_agent or self.config.user_agent)

    def reverse_geocode(
        self,
        lat: float,
        lon: float,
        language_tag: str = "en",
        zoom_level: NarrationDetailLevel = NarrationDetailLevel.DETAILED,
    ) -> LocationAddress:
        try:
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
