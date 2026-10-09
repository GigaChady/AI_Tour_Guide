from __future__ import annotations

import logging

from narration.location_discovery.address_resolution_task import AddressResolutionTask
from narration.location_discovery.contracts import GeocodingClient, PoiDataClient, PoiParser
from narration.location_discovery.nearby_poi_discovery_task import NearbyPoiDiscoveryTask
from narration.schemas import (
    LocationAddress,
    LocationDiscoveryResult,
    NarrationDetailLevel,
    NarrationSettings,
    PoiCandidate,
)

logger = logging.getLogger(__name__)


class LocationDiscoveryTask:
    def __init__(
        self,
        geocoding_client: GeocodingClient,
        poi_data_client: PoiDataClient,
        poi_parser: PoiParser,
        address_resolution_task: AddressResolutionTask | None = None,
        nearby_poi_discovery_task: NearbyPoiDiscoveryTask | None = None,
    ):
        self.address_resolution_task = address_resolution_task or AddressResolutionTask(
            geocoding_client=geocoding_client,
        )
        self.nearby_poi_discovery_task = (
            nearby_poi_discovery_task
            or NearbyPoiDiscoveryTask(
                poi_data_client=poi_data_client,
                poi_parser=poi_parser,
            )
        )

    def get_address(
        self,
        lat: float,
        lon: float,
        language_tag: str = "en",
        zoom_level: NarrationDetailLevel = NarrationDetailLevel.DETAILED,
    ) -> LocationAddress:
        return self.address_resolution_task.run(
            lat=lat,
            lon=lon,
            language_tag=language_tag,
            zoom_level=zoom_level,
        )

    def get_nearby_pois(
        self,
        lat: float,
        lon: float,
        radius: int = 50,
    ) -> list[PoiCandidate]:
        return self.nearby_poi_discovery_task.run(lat=lat, lon=lon, radius=radius)

    def get_location_details(
        self,
        narration_settings: NarrationSettings,
    ) -> LocationDiscoveryResult:
        logger.info("Starting location processing")
        address = self.get_address(
            lat=narration_settings.latitude,
            lon=narration_settings.longitude,
            language_tag=narration_settings.language.language_tag,
            zoom_level=narration_settings.detail_level,
        )
        candidates = self.get_nearby_pois(
            lat=narration_settings.latitude,
            lon=narration_settings.longitude,
            radius=narration_settings.search_radius,
        )
        logger.info("Finished location processing")
        return LocationDiscoveryResult(address=address, candidates=candidates)
