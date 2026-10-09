from __future__ import annotations

import logging

from narration.location_discovery.contracts import PoiDataClient, PoiParser
from narration.schemas import PoiCandidate

logger = logging.getLogger(__name__)


class NearbyPoiDiscoveryTask:
    def __init__(
        self,
        poi_data_client: PoiDataClient,
        poi_parser: PoiParser,
    ):
        self.poi_data_client = poi_data_client
        self.poi_parser = poi_parser

    def run(
        self,
        lat: float,
        lon: float,
        radius: int = 50,
    ) -> list[PoiCandidate]:
        data = self.poi_data_client.get_nearby_poi_data(
            lat=lat,
            lon=lon,
            radius=radius,
        )
        if data is None:
            return []

        pois = self.poi_parser.parse(data)

        if not pois:
            logger.warning(
                "No POIs found nearby lat=%s lon=%s radius=%s",
                lat,
                lon,
                radius,
            )

        return pois
