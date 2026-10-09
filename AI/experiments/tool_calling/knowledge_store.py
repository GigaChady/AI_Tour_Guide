from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

from experiments.tool_calling.contracts import (
    KnowledgeChunk,
    LocationContext,
    Place,
    ResearchArea,
    SearchResult,
    StoreResult,
)


def _normalised_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


class InMemoryKnowledgeStore:
    def __init__(self):
        self.places: dict[str, Place] = {}
        self.chunks: dict[str, KnowledgeChunk] = {}
        self.research_areas: dict[str, ResearchArea] = {}
        self.sources: dict[str, SearchResult] = {}

    def get_area_coverage(
        self,
        location: LocationContext,
        radius_m: int = 900,
    ) -> dict[str, Any]:
        best: ResearchArea | None = None
        for area in self.research_areas.values():
            distance = _haversine_m(
                location.lat,
                location.lon,
                area.center_lat,
                area.center_lon,
            )
            if distance <= max(radius_m, area.radius_m):
                best = area
                break
        if best is None:
            return {
                "researched": False,
                "research_count": 0,
                "chunk_count": 0,
                "coverage_level": "missing",
            }
        level = "sufficient" if best.chunk_count >= 4 else "weak"
        return {
            "researched": True,
            "research_count": best.research_count,
            "chunk_count": best.chunk_count,
            "coverage_level": level,
            "area_id": best.area_id,
            "name": best.name,
        }

    def search_nearby(
        self,
        location: LocationContext,
        radius_m: int = 2_500,
        preferences: list[str] | None = None,
        exclude_chunk_ids: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        preferences = preferences or []
        excluded = set(exclude_chunk_ids or [])
        location_names = {
            _normalised_key(location.neighbourhood),
            _normalised_key(location.district),
            _normalised_key(location.city),
        }
        ranked: list[tuple[float, KnowledgeChunk, float]] = []
        for chunk in self.chunks.values():
            if chunk.chunk_id in excluded:
                continue
            if chunk.lat is not None and chunk.lon is not None:
                distance = _haversine_m(location.lat, location.lon, chunk.lat, chunk.lon)
            elif _normalised_key(chunk.area_name) in location_names:
                distance = 0.0
            else:
                continue
            if distance > radius_m:
                continue
            text = _normalised_key(f"{chunk.topic} {chunk.content}")
            preference_hits = sum(
                _normalised_key(preference) in text for preference in preferences
            )
            score = 1.0 - distance / radius_m + 0.25 * preference_hits + 0.2 * chunk.confidence
            ranked.append((score, chunk, distance))
        ranked.sort(key=lambda row: row[0], reverse=True)
        return [
            {**chunk.to_dict(), "distance_m": round(distance), "score": round(score, 3)}
            for score, chunk, distance in ranked[: max(1, min(limit, 20))]
        ]

    def store_research(
        self,
        location: LocationContext,
        places: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
        allowed_source_ids: set[str],
        source_catalog: dict[str, SearchResult],
        radius_m: int = 900,
    ) -> StoreResult:
        result = StoreResult()
        place_by_name: dict[str, Place] = {}

        for raw_place in places:
            canonical_name = str(raw_place.get("canonical_name") or "").strip()
            if not canonical_name:
                result.validation_errors.append("Place without canonical_name was rejected")
                continue
            place_id = _stable_id("place", canonical_name)
            place = Place(
                place_id=place_id,
                canonical_name=canonical_name,
                aliases=sorted({str(x).strip() for x in raw_place.get("aliases", []) if str(x).strip()}),
                lat=float(raw_place["lat"]) if raw_place.get("lat") is not None else None,
                lon=float(raw_place["lon"]) if raw_place.get("lon") is not None else None,
            )
            self.places[place_id] = place
            place_by_name[_normalised_key(canonical_name)] = place
            result.stored_place_ids.append(place_id)

        for index, raw_chunk in enumerate(chunks, start=1):
            anchor_type = str(raw_chunk.get("anchor_type") or "").upper()
            anchor_name = str(raw_chunk.get("anchor_name") or "").strip()
            canonical_name = str(raw_chunk.get("canonical_name") or anchor_name).strip()
            topic = str(raw_chunk.get("topic") or "").strip()
            content = str(raw_chunk.get("content") or "").strip()
            source_ids = sorted({str(x) for x in raw_chunk.get("source_ids", [])})
            unknown_sources = set(source_ids) - allowed_source_ids

            errors = []
            if anchor_type not in {"PLACE", "AREA"}:
                errors.append("anchor_type must be PLACE or AREA")
            if not anchor_name or not topic or not content:
                errors.append("anchor_name, topic and content are required")
            if not source_ids:
                errors.append("at least one source_id is required")
            if unknown_sources:
                errors.append(f"unknown source_ids: {sorted(unknown_sources)}")
            if errors:
                result.validation_errors.append(f"Chunk {index}: {'; '.join(errors)}")
                continue

            chunk_id = _stable_id("chunk", anchor_type, canonical_name, topic, content)
            if chunk_id in self.chunks:
                result.duplicates_skipped += 1
                continue
            matching_place = place_by_name.get(_normalised_key(canonical_name))
            lat = raw_chunk.get("lat")
            lon = raw_chunk.get("lon")
            if matching_place:
                lat = matching_place.lat if lat is None else lat
                lon = matching_place.lon if lon is None else lon
            chunk = KnowledgeChunk(
                chunk_id=chunk_id,
                anchor_type=anchor_type,
                anchor_name=anchor_name,
                canonical_name=canonical_name,
                aliases=sorted({str(x).strip() for x in raw_chunk.get("aliases", []) if str(x).strip()}),
                topic=topic,
                content=content,
                source_ids=source_ids,
                lat=float(lat) if lat is not None else None,
                lon=float(lon) if lon is not None else None,
                area_name=location.neighbourhood or location.district or location.city,
                confidence=max(0.0, min(1.0, float(raw_chunk.get("confidence", 0.5)))),
            )
            self.chunks[chunk_id] = chunk
            result.stored_chunk_ids.append(chunk_id)
            for source_id in source_ids:
                self.sources[source_id] = source_catalog[source_id]

        if result.stored_chunk_ids:
            area_name = location.neighbourhood or location.district or location.city
            area_id = _stable_id(
                "area",
                area_name,
                f"{location.lat:.3f}",
                f"{location.lon:.3f}",
            )
            previous = self.research_areas.get(area_id)
            self.research_areas[area_id] = ResearchArea(
                area_id=area_id,
                name=area_name,
                center_lat=location.lat,
                center_lon=location.lon,
                radius_m=radius_m,
                research_count=(previous.research_count if previous else 0) + 1,
                chunk_count=sum(
                    chunk.area_name == area_name for chunk in self.chunks.values()
                ),
            )
        return result

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "places": [value.to_dict() for value in self.places.values()],
            "chunks": [value.to_dict() for value in self.chunks.values()],
            "sources": [value.to_dict() for value in self.sources.values()],
            "research_areas": [value.to_dict() for value in self.research_areas.values()],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
