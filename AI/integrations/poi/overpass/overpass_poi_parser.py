from __future__ import annotations

from integrations.poi.overpass.overpass_models import OverpassResponse
from narration.schemas import PoiCandidate


class OverpassPoiParser:
    def __init__(self, ignored_types: set[str] | None = None):
        self.ignored_types = ignored_types or {
            "information",
            "hotel",
            "guest_house",
            "picnic_site",
        }

    def parse(self, response: OverpassResponse) -> list[PoiCandidate]:
        pois = []

        for element in response.elements:
            tags = element.get("tags", {})
            name = tags.get("name")
            poi_type = tags.get("tourism") or tags.get("historic")

            if not name or poi_type in self.ignored_types:
                continue

            lat = element.get("lat") or element.get("center", {}).get("lat")
            lon = element.get("lon") or element.get("center", {}).get("lon")

            if lat is None or lon is None:
                continue

            pois.append(
                PoiCandidate(
                    name=name,
                    category=poi_type,
                    lat=lat,
                    lon=lon,
                    website=tags.get("website"),
                    wikidata=tags.get("wikidata"),
                    wikipedia=tags.get("wikipedia"),
                    description=tags.get("description"),
                )
            )

        deduplicated = {}
        for poi in pois:
            key = (poi.name.strip().lower(), poi.category)
            deduplicated[key] = poi

        return list(deduplicated.values())
