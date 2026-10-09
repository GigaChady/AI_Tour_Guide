from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LocationContext:
    lat: float
    lon: float
    street: str = ""
    neighbourhood: str = ""
    district: str = ""
    city: str = ""
    country: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    source_id: str
    title: str
    url: str
    snippet: str
    query: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Coordinates:
    lat: float
    lon: float
    display_name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Place:
    place_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    lat: float | None = None
    lon: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeChunk:
    chunk_id: str
    anchor_type: str
    anchor_name: str
    canonical_name: str
    topic: str
    content: str
    source_ids: list[str]
    aliases: list[str] = field(default_factory=list)
    lat: float | None = None
    lon: float | None = None
    area_name: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchArea:
    area_id: str
    name: str
    center_lat: float
    center_lon: float
    radius_m: int
    research_count: int
    chunk_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StoreResult:
    stored_chunk_ids: list[str] = field(default_factory=list)
    stored_place_ids: list[str] = field(default_factory=list)
    duplicates_skipped: int = 0
    validation_errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return bool(self.stored_chunk_ids) and not self.validation_errors

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "success": self.success}


@dataclass
class ToolTraceEntry:
    step: int
    tool_name: str
    arguments: dict[str, Any]
    result: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRun:
    location: LocationContext | None
    store_result: StoreResult
    trace: list[ToolTraceEntry]
    latency_s: float
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location.to_dict() if self.location else None,
            "store_result": self.store_result.to_dict(),
            "trace": [entry.to_dict() for entry in self.trace],
            "latency_s": self.latency_s,
            "usage": self.usage,
        }
