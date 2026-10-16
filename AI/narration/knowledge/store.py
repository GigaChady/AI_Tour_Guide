from __future__ import annotations

import hashlib
import uuid
from threading import RLock

from narration.knowledge.models import (
    GeocodedPlace,
    KnowledgeChunk,
    KnowledgeDraft,
    Place,
    PlaceAlias,
    PlaceCandidate,
    PlaceResolution,
    ResolutionStatus,
    Scope,
    Source,
)
from narration.knowledge.normalization import normalized_name, normalized_text
from narration.knowledge.place_resolver import PlaceResolver


class InMemoryKnowledgeStore:
    """One shared, thread-safe store for notebook research workers."""

    def __init__(self, resolver: PlaceResolver | None = None):
        self._resolver = resolver or PlaceResolver()
        self._lock = RLock()
        self._sources: dict[str, Source] = {}
        self._places: dict[str, Place] = {}
        self._chunks: dict[str, KnowledgeChunk] = {}

    @property
    def sources(self) -> list[Source]:
        with self._lock:
            return [source.model_copy(deep=True) for source in self._sources.values()]

    @property
    def places(self) -> list[Place]:
        with self._lock:
            return [place.model_copy(deep=True) for place in self._places.values()]

    @property
    def chunks(self) -> list[KnowledgeChunk]:
        with self._lock:
            return [chunk.model_copy(deep=True) for chunk in self._chunks.values()]

    def add_source(self, source: Source) -> Source:
        with self._lock:
            existing = self._sources.get(source.source_id)
            if existing is not None and (
                existing.provider != source.provider or existing.url != source.url
            ):
                raise ValueError(f"conflicting source_id: {source.source_id}")
            if existing is None:
                self._sources[source.source_id] = source.model_copy(deep=True)
            elif source.evidence_text:
                if existing.evidence_text in source.evidence_text:
                    existing.evidence_text = source.evidence_text
                elif source.evidence_text not in existing.evidence_text:
                    existing.evidence_text += "\n" + source.evidence_text
            return self._sources[source.source_id].model_copy(deep=True)

    def resolve_place(self, candidate: PlaceCandidate) -> PlaceResolution:
        with self._lock:
            self._require_sources(candidate.source_ids)
            for alias in candidate.aliases:
                alias_source_ids = alias.source_ids or [alias.source_id]
                if not set(alias_source_ids).issubset(candidate.source_ids):
                    raise ValueError(f"alias source is not cited by candidate: {alias_source_ids}")

            decision = self._resolver.resolve(candidate, list(self._places.values()))
            if decision.place_id is not None:
                place = self._places[decision.place_id]
                self._merge_candidate(place, candidate)
                status = ResolutionStatus.MATCHED
            else:
                place = Place(
                    place_id=str(uuid.uuid4()),
                    canonical_name=candidate.name,
                    city=candidate.city,
                    street=candidate.street,
                    aliases=self._distinct_aliases(candidate.aliases, candidate.name),
                    external_ids=dict(candidate.external_ids),
                    locations=self._candidate_locations(candidate),
                    source_ids=sorted(set(candidate.source_ids)),
                    lat=candidate.lat,
                    lon=candidate.lon,
                    coordinate_source=candidate.coordinate_source,
                )
                self._places[place.place_id] = place
                status = (
                    ResolutionStatus.CREATED_UNCERTAIN
                    if decision.possible_match_ids
                    else ResolutionStatus.CREATED
                )
            return PlaceResolution(
                place=place.model_copy(deep=True),
                status=status,
                reason=decision.reason,
                possible_match_ids=decision.possible_match_ids,
            )

    def add_chunk(self, draft: KnowledgeDraft) -> KnowledgeChunk:
        with self._lock:
            self._require_sources(draft.source_ids)
            if draft.scope == Scope.PLACE and not draft.place_id:
                raise ValueError("PLACE chunk requires a resolved place_id")
            if draft.place_id and draft.place_id not in self._places:
                raise ValueError(f"unknown place_id: {draft.place_id}")

            place = self._places.get(draft.place_id) if draft.place_id else None
            if place and draft.city and normalized_name(draft.city) != normalized_name(place.city):
                raise ValueError("PLACE chunk city conflicts with resolved place")
            anchor = draft.place_id or ":".join(
                normalized_name(part)
                for part in (draft.anchor_name, draft.city, draft.region, draft.country)
            )
            identity = "|".join(
                [draft.scope.value, anchor, normalized_name(draft.topic), normalized_text(draft.content)]
            )
            chunk_id = "chunk:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            existing = self._chunks.get(chunk_id)
            if existing is not None:
                existing.source_ids = sorted(set(existing.source_ids) | set(draft.source_ids))
                existing.source_urls = sorted(
                    set(existing.source_urls) | {
                        self._sources[source_id].url for source_id in draft.source_ids
                    }
                )
                existing.source_workers = sorted(
                    set(existing.source_workers) | {draft.source_worker}
                )
                return existing.model_copy(deep=True)

            fields = draft.model_dump(exclude={"source_ids"})
            if place:
                fields["city"] = place.city
            chunk = KnowledgeChunk(
                **fields,
                chunk_id=chunk_id,
                source_ids=sorted(set(draft.source_ids)),
                source_urls=sorted({self._sources[source_id].url for source_id in draft.source_ids}),
                source_workers=[draft.source_worker],
            )
            self._chunks[chunk_id] = chunk
            return chunk.model_copy(deep=True)

    def _require_sources(self, source_ids: list[str]) -> None:
        unknown = set(source_ids) - self._sources.keys()
        if unknown:
            raise ValueError(f"unknown source_ids: {sorted(unknown)}")

    @staticmethod
    def _distinct_aliases(aliases: list[PlaceAlias], canonical_name: str) -> list[PlaceAlias]:
        canonical_key = normalized_name(canonical_name)
        distinct: dict[tuple[str, tuple[str, ...]], PlaceAlias] = {}
        for alias in aliases:
            key = (normalized_name(alias.name), tuple(sorted(alias.source_ids or [alias.source_id])))
            if key[0] and key[0] != canonical_key:
                distinct[key] = alias.model_copy(deep=True)
        return list(distinct.values())

    @staticmethod
    def _candidate_locations(candidate: PlaceCandidate) -> list[GeocodedPlace]:
        locations = list(candidate.locations)
        if candidate.lat is not None and not any(
            point.coordinate_source == candidate.coordinate_source for point in locations
        ):
            locations.append(GeocodedPlace(
                name=candidate.name, city=candidate.city, street=candidate.street,
                lat=candidate.lat, lon=candidate.lon,
                coordinate_source=candidate.coordinate_source,
                external_ids=dict(candidate.external_ids),
            ))
        return [point.model_copy(deep=True) for point in locations]

    def _merge_candidate(self, place: Place, candidate: PlaceCandidate) -> None:
        new_aliases = list(candidate.aliases)
        if normalized_name(candidate.name) != normalized_name(place.canonical_name):
            new_aliases.append(
                PlaceAlias(name=candidate.name, source_ids=candidate.source_ids)
            )
        place.aliases = self._distinct_aliases(
            [*place.aliases, *new_aliases], place.canonical_name
        )
        place.source_ids = sorted(set(place.source_ids) | set(candidate.source_ids))
        place.external_ids.update(candidate.external_ids)
        locations_by_source = {point.coordinate_source: point for point in place.locations}
        for point in self._candidate_locations(candidate):
            locations_by_source[point.coordinate_source] = point
        place.locations = list(locations_by_source.values())
        if place.lat is None and candidate.lat is not None:
            place.lat, place.lon = candidate.lat, candidate.lon
            place.coordinate_source = candidate.coordinate_source
        if not place.street and candidate.street:
            place.street = candidate.street
