from __future__ import annotations

import hashlib
import re
from enum import Enum
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Scope(str, Enum):
    PLACE = "PLACE"
    STREET = "STREET"
    DISTRICT = "DISTRICT"
    CITY = "CITY"
    REGION = "REGION"
    COUNTRY = "COUNTRY"


class ResolutionStatus(str, Enum):
    MATCHED = "matched"
    CREATED = "created"
    CREATED_UNCERTAIN = "created_uncertain"


class _KnowledgeModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class _OptionalCoordinates(_KnowledgeModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    coordinate_source: str = ""

    @model_validator(mode="after")
    def coordinates_are_a_pair(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must both be supplied or both be absent")
        if self.lat is not None and not self.coordinate_source:
            raise ValueError("coordinates require a coordinate_source")
        if self.lat is None and self.coordinate_source:
            raise ValueError("coordinate_source requires coordinates")
        return self


class LocationContext(_KnowledgeModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    street: str = ""
    neighbourhood: str = ""
    district: str = ""
    city: str = ""
    region: str = ""
    country: str = ""


def _canonical_source_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source URL must be an absolute HTTP(S) URL")
    return urlunsplit(
        (parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path or "/", parsed.query, "")
    )


def make_source_id(provider: str, url: str) -> str:
    """Namespace a document identity by provider to avoid cross-worker collisions."""
    provider_key = provider.strip().casefold()
    if not provider_key or not _PROVIDER_PATTERN.fullmatch(provider_key):
        raise ValueError("provider must contain letters, digits, underscores or hyphens")
    canonical_url = _canonical_source_url(url)
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:20]
    return f"{provider_key}:{digest}"


_PROVIDER_PATTERN = re.compile(r"[a-z0-9_-]+")


class Source(_KnowledgeModel):
    source_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    evidence_text: str = ""

    @model_validator(mode="after")
    def source_id_matches_document(self):
        if self.source_id != make_source_id(self.provider, self.url):
            raise ValueError("source_id must match provider and URL")
        self.url = _canonical_source_url(self.url)
        return self

    @classmethod
    def from_url(
        cls, *, provider: str, title: str, url: str, evidence_text: str = ""
    ) -> "Source":
        return cls(
            source_id=make_source_id(provider, url),
            provider=provider,
            title=title,
            url=url,
            evidence_text=evidence_text,
        )


class PlaceAlias(_KnowledgeModel):
    name: str = Field(min_length=1)
    source_id: str = ""
    source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def has_source(self):
        if not self.source_id and not self.source_ids:
            raise ValueError("alias requires a source or source batch")
        return self


class GeocodedPlace(_KnowledgeModel):
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    coordinate_source: str = Field(min_length=1)
    city: str = ""
    country: str = ""
    street: str = ""
    district: str = ""
    aliases: list[str] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)


class PlaceCandidate(_OptionalCoordinates):
    name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    street: str = ""
    aliases: list[PlaceAlias] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)
    locations: list[GeocodedPlace] = Field(default_factory=list)
    source_ids: list[str] = Field(min_length=1)


class Place(_OptionalCoordinates):
    place_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    street: str = ""
    aliases: list[PlaceAlias] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)
    locations: list[GeocodedPlace] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class PlaceResolution(_KnowledgeModel):
    place: Place
    status: ResolutionStatus
    reason: str
    possible_match_ids: list[str] = Field(default_factory=list)


class KnowledgeDraft(_KnowledgeModel):
    scope: Scope
    anchor_name: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    source_worker: str = Field(min_length=1)
    place_id: str | None = None
    city: str = ""
    region: str = ""
    country: str = ""

    @model_validator(mode="after")
    def local_scope_has_city(self):
        if self.scope in {Scope.STREET, Scope.DISTRICT} and not self.city:
            raise ValueError("STREET and DISTRICT chunks require city context")
        if self.scope != Scope.PLACE and self.place_id is not None:
            raise ValueError("only PLACE chunks may reference place_id")
        return self


class KnowledgeChunk(KnowledgeDraft):
    chunk_id: str = Field(min_length=1)
    source_urls: list[str] = Field(default_factory=list)
    source_workers: list[str] = Field(default_factory=list)


class ResearchArea(_KnowledgeModel):
    area_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    center_lat: float = Field(ge=-90, le=90)
    center_lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(gt=0)
    research_count: int = Field(default=0, ge=0)
    chunk_count: int = Field(default=0, ge=0)
