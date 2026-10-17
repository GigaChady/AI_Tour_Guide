from __future__ import annotations

import math
import struct
from threading import RLock
from typing import Callable

from narration.knowledge.models import GeocodedPlace, LocationContext, PlaceCandidate
from narration.knowledge.normalization import normalized_name
from narration.knowledge.place_location_config import PlaceLocationConfig


def _point_from_wkb(value: bytes | None) -> tuple[float, float] | None:
    if not value or len(value) < 21:
        return None
    order = "<" if value[0] == 1 else ">" if value[0] == 0 else ""
    if not order or struct.unpack(f"{order}I", value[1:5])[0] != 1:
        return None
    lon, lat = struct.unpack(f"{order}dd", value[5:21])
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        return None
    return lat, lon


def _common_names(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [name for part in value.values() for name in _common_names(part)]
    if isinstance(value, (list, tuple)):
        return [name for part in value for name in _common_names(part)]
    return []


class OverturePlacesClient:
    """Query Overture Places around the research city and cache that area."""

    def __init__(
        self, *, config: PlaceLocationConfig | None = None,
        record_reader: Callable | None = None,
    ):
        self.config = config or PlaceLocationConfig()
        self.record_reader = record_reader
        self._lock = RLock()
        self._cache: dict[tuple[float, float], list[dict]] = {}

    def search_place(
        self, candidate: PlaceCandidate, *, research_location: LocationContext,
        limit: int = 5,
    ) -> list[GeocodedPlace]:
        # A local spatial extract cannot locate an unrelated city. The resolver
        # continues with global Nominatim in that case.
        if normalized_name(candidate.city) != normalized_name(research_location.city):
            return []
        if not 1 <= limit <= 20:
            raise ValueError("Overture result limit must be between 1 and 20")
        rows = self._places_near(research_location.lat, research_location.lon)
        sought = {normalized_name(candidate.name)} | {
            normalized_name(alias.name) for alias in candidate.aliases
        }
        matches: list[tuple[int, GeocodedPlace]] = []
        for row in rows:
            names = row.get("names") or {}
            if not isinstance(names, dict):
                continue
            primary = names.get("primary")
            if not isinstance(primary, str) or not primary.strip():
                continue
            aliases = [name for name in _common_names(names.get("common")) if name != primary]
            found = {normalized_name(primary)} | {normalized_name(name) for name in aliases}
            if not sought & found:
                continue
            addresses = row.get("addresses") or []
            locality = ""
            if isinstance(addresses, list):
                locality = next((str(part.get("locality")) for part in addresses
                                 if isinstance(part, dict) and part.get("locality")), "")
            if locality and normalized_name(locality) != normalized_name(candidate.city):
                continue
            point = _point_from_wkb(row.get("geometry"))
            if point is None or not row.get("id"):
                continue
            score = 2 if normalized_name(primary) in sought else 1
            matches.append((score, GeocodedPlace(
                name=primary, aliases=aliases, lat=point[0], lon=point[1],
                city=locality or candidate.city, country=research_location.country,
                coordinate_source=f"overture:{row['id']}",
                external_ids={"overture": str(row["id"])},
            )))
        matches.sort(key=lambda entry: -entry[0])
        return [point for _, point in matches[:limit]]

    def _places_near(self, lat: float, lon: float) -> list[dict]:
        key = (lat, lon)
        with self._lock:
            if key not in self._cache:
                if self.record_reader is None:
                    try:
                        from overturemaps import record_batch_reader
                    except ImportError as exc:
                        raise RuntimeError("Install overturemaps to query Overture Places") from exc
                    reader_factory = record_batch_reader
                else:
                    reader_factory = self.record_reader
                lat_offset = self.config.overture_radius_km / 111.0
                lon_offset = self.config.overture_radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
                bbox = (lon - lon_offset, lat - lat_offset,
                        lon + lon_offset, lat + lat_offset)
                reader = reader_factory("place", bbox=bbox)
                self._cache[key] = reader.read_all().to_pylist() if reader is not None else []
            return self._cache[key]
