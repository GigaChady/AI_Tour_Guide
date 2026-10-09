from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from narration.schemas.narration import NarrationSettings


class PoiCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    category: str
    lat: float
    lon: float
    website: str | None = None
    wikidata: str | None = None
    wikipedia: str | None = None
    description: str | None = None


class LocationAddress(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def city(self) -> str:
        address = self.raw.get("address", {})
        return address.get("city", "")

    @property
    def suburb(self) -> str:
        address = self.raw.get("address", {})
        return address.get("suburb", "")

    @property
    def general_location(self) -> str:
        address = self.raw.get("address", {})
        location_parts = [
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality"),
            address.get("state") or address.get("region"),
            address.get("country"),
        ]
        return ", ".join(part for part in location_parts if part)


class LocationDiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    address: LocationAddress = Field(default_factory=LocationAddress)
    candidates: list[PoiCandidate] = Field(default_factory=list)


class SelectedPoi(BaseModel):
    model_config = ConfigDict(extra="ignore")

    poi: PoiCandidate
    distance_km: float
    category_rank: int


class PoiInformationSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    content: str
    source_type: str = "web_search"


class EnrichedPoi(BaseModel):
    model_config = ConfigDict(extra="ignore")

    poi: PoiCandidate
    address: LocationAddress = Field(default_factory=LocationAddress)
    information_sources: list[PoiInformationSource] = Field(default_factory=list)

    def to_context_text(self) -> str:
        poi_fields = [
            f"Name: {self.poi.name}",
            f"Type/category: {self.poi.category}",
            f"Location: {self.address.general_location or 'Unknown'}",
        ]
        if self.poi.description:
            poi_fields.append(f"Description: {self.poi.description}")

        source_sections = []
        for index, source in enumerate(self.information_sources, start=1):
            source_sections.append(
                "\n".join(
                    [
                        f"Information source {index}:",
                        source.content or "No content found.",
                    ]
                )
            )

        if not source_sections:
            source_sections.append("No external information sources found.")

        return "\n".join(poi_fields) + "\n\n" + "\n\n".join(source_sections)


class FilteredPoiFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    poi: PoiCandidate
    facts: str


class NarrationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    location: str
    narration: str

    @classmethod
    def from_model_response(cls, value: dict[str, Any] | str) -> "NarrationResult":
        if isinstance(value, dict):
            return cls(
                location=str(value.get("location", "")),
                narration=str(value.get("narration", "")),
            )

        return cls(location="", narration=value)


class TourPipelineResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    selected_poi: SelectedPoi | None = None
    selected_pois: list[SelectedPoi] = Field(default_factory=list)
    enriched_poi: EnrichedPoi | None = None
    filtered_facts: FilteredPoiFacts | None = None
    narration: NarrationResult | None = None

    @property
    def poi(self) -> PoiCandidate | None:
        if self.selected_poi is None:
            return None
        return self.selected_poi.poi


class NarrationPipelineRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(min_length=1)
    settings: NarrationSettings
