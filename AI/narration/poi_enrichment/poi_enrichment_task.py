from __future__ import annotations

import logging

from narration.schemas import (
    EnrichedPoi,
    LocationAddress,
    PoiInformationSource,
    SelectedPoi,
)
from narration.poi_enrichment.contracts import SearchClient

logger = logging.getLogger(__name__)


def _quoted(value: str) -> str:
    value = value.strip()
    return f'"{value}"' if value else ""


def _general_location(address: LocationAddress) -> str:
    return address.general_location.replace(",", "")


class PoiEnrichmentTask:
    def __init__(self, search_client: SearchClient):
        self.search_client = search_client

    def run(
        self,
        selected_poi: SelectedPoi,
        address: LocationAddress,
    ) -> EnrichedPoi:
        query = self._build_query(selected_poi=selected_poi, address=address)
        try:
            if hasattr(self.search_client, "search_poi"):
                search_content = self.search_client.search_poi(selected_poi, address)
            else:
                search_content = self.search_client.search(query)
        except Exception as e:
            logger.warning(
                "Search failed for POI '%s' query='%s': %s",
                selected_poi.poi.name,
                query,
                e,
            )
            search_content = ""

        if not search_content:
            search_content = self._fallback_context(
                selected_poi=selected_poi,
                address=address,
            )
            logger.info(
                "Using fallback context for POI '%s' query='%s'",
                selected_poi.poi.name,
                query,
            )

        logger.info(
            "Raw location information for POI '%s' query='%s': %s",
            selected_poi.poi.name,
            query,
            search_content[:500],
        )

        return EnrichedPoi(
            poi=selected_poi.poi,
            address=address,
            information_sources=[
                PoiInformationSource(
                    query=query,
                    content=search_content,
                    source_type=getattr(self.search_client, "source_type", "web_search"),
                )
            ],
        )

    @staticmethod
    def _build_query(selected_poi: SelectedPoi, address: LocationAddress) -> str:
        query_parts = [
            _quoted(selected_poi.poi.name),
            _quoted(_general_location(address)),
        ]
        return " ".join(part for part in query_parts if part)

    @staticmethod
    def _fallback_context(selected_poi: SelectedPoi, address: LocationAddress) -> str:
        poi = selected_poi.poi
        context_parts = [
            f"POI name: {poi.name}",
            f"POI category: {poi.category}",
        ]
        if address.general_location:
            context_parts.append(f"General location: {address.general_location}")
        if poi.description:
            context_parts.append(f"Available description: {poi.description}")
        context_parts.append(
            "External web search failed, so use only the available POI metadata. "
            "Avoid inventing exact historical facts."
        )
        return "\n".join(context_parts)
