from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from narration.knowledge.address_evidence import (
    SupportedAddress, normalized_address_street, supported_address,
)
from narration.knowledge.models import GeocodedPlace, LocationContext, PlaceAlias, PlaceCandidate
from narration.knowledge.normalization import normalized_name
from narration.knowledge.place_location_config import PlaceLocationConfig
from narration.knowledge.place_location_resolver import (
    AddressSearchClient, OverturePlaceClient, PlaceSearchClient, WikimediaPlaceClient,
)


class _AddressArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    address: str = Field(min_length=1)
    city: str = Field(min_length=1)
    country: str = ""


class _PlaceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    city: str = Field(min_length=1)
    country: str = ""


class GeocodingToolbox:
    """Two read-only tools that expose geocoder candidates to a model."""

    def __init__(
        self, *, address_client: AddressSearchClient | None,
        overture_client: OverturePlaceClient | None,
        nominatim_client: PlaceSearchClient,
        wikimedia_client: WikimediaPlaceClient | None,
        research_location: LocationContext,
        source_text: str,
        candidate_city: str,
        config: PlaceLocationConfig | None = None,
    ):
        self.address_client = address_client
        self.overture_client = overture_client
        self.nominatim_client = nominatim_client
        self.wikimedia_client = wikimedia_client
        self.research_location = research_location
        self.source_text = source_text
        self.candidate_city = candidate_city
        self.config = config or PlaceLocationConfig()
        self.candidates: dict[str, GeocodedPlace] = {}
        self._ids_by_source: dict[str, str] = {}

    @staticmethod
    def schemas() -> list[dict[str, Any]]:
        return [{"type": "function", "function": {
            "name": "geocode_address",
            "description": "Find numbered address points supported by the research text. A short numeric range may return several points.",
            "parameters": {"type": "object", "properties": {
                "address": {"type": "string"}, "city": {"type": "string"},
                "country": {"type": "string"},
            }, "required": ["address", "city", "country"], "additionalProperties": False},
        }}, {"type": "function", "function": {
            "name": "search_place",
            "description": "Search Wikipedia, Overture Places and Nominatim by place name and aliases. Returns candidates, not a decision.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"},
                "aliases": {"type": "array", "items": {"type": "string"}},
                "city": {"type": "string"}, "country": {"type": "string"},
            }, "required": ["name", "aliases", "city", "country"],
                "additionalProperties": False},
        }}]

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "geocode_address":
            return self.geocode_address(**_AddressArgs.model_validate(arguments).model_dump())
        if name == "search_place":
            return self.search_place(**_PlaceArgs.model_validate(arguments).model_dump())
        raise ValueError(f"Unknown geocoding tool: {name}")

    def _output(self, point: GeocodedPlace) -> dict[str, Any]:
        identifier = self._ids_by_source.get(point.coordinate_source)
        if identifier is None:
            identifier = f"geo_{len(self.candidates) + 1}"
            self._ids_by_source[point.coordinate_source] = identifier
            self.candidates[identifier] = point
        return {"candidate_id": identifier, **point.model_dump()}

    def _address_parts(self, value: str, city: str) -> tuple[list[SupportedAddress], str]:
        single, reason = supported_address(
            value, city=city, source_text=self.source_text,
            max_chars=self.config.max_address_chars,
        )
        if single is not None:
            return [single], "supported"
        if reason != "multiple house numbers":
            return [], reason
        # Expand only a short, explicitly sourced numeric range. A slash or a
        # list of unrelated addresses stays unresolved for model review.
        match = re.fullmatch(
            r"(?P<street>.+?)\s+(?P<start>\d{1,4})\s*[-–—]\s*(?P<end>\d{1,4})(?:,\s*(?P<city>.+))?",
            value.strip(),
        )
        if match is None:
            return [], "unsupported address range"
        if match.group("city") and normalized_name(city) not in normalized_name(match.group("city")):
            return [], "address city differs from place city"
        street = re.sub(
            r"^(?:ul\.?|ulica|al\.?|aleja|aleje|pl\.?|plac|os\.?|osiedle)\s+",
            "", match.group("street").strip(), flags=re.IGNORECASE,
        ).strip()
        street_key = normalized_address_street(street)
        first, last = int(match.group("start")), int(match.group("end"))
        if (not street_key or last < first
                or last - first + 1 > self.config.max_address_range_points):
            return [], "address range is too large or invalid"
        evidence = normalized_name(self.source_text)
        phrase = f"{street_key} {first} {last}"
        if phrase not in evidence:
            return [], "address range was not found in source text"
        return [SupportedAddress(street, str(number), city)
                for number in range(first, last + 1)], "supported range"

    def geocode_address(self, address: str, city: str, country: str = "") -> dict[str, Any]:
        if self.address_client is None:
            return {"status": "unavailable", "results": [], "errors": ["Address geocoder is not configured"]}
        country_keys = {normalized_name(country), normalized_name(self.research_location.country)}
        if (normalized_name(city) != normalized_name(self.candidate_city)
                or (country and len(country_keys) > 1
                    and country_keys != {"poland", "polska"})):
            return {"status": "invalid", "results": [], "errors": ["Address city/country differs from this place"]}
        addresses, reason = self._address_parts(address, city)
        if not addresses:
            return {"status": "invalid", "results": [], "errors": [reason]}
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        for part in addresses:
            try:
                found = self.address_client.search_address(part, country=country)
            except Exception as exc:
                errors.append(f"GUS: {type(exc).__name__}: {exc}")
                continue
            for point in found:
                if (point.location_type == "address"
                        and normalized_name(point.city) == normalized_name(city)
                        and normalized_address_street(point.street) == normalized_address_street(part.street)
                        and normalized_name(point.house_number) == normalized_name(part.house_number)):
                    results.append(self._output(point))
        return {"status": "partial_error" if errors else "ok", "results": results,
                "errors": errors, "note": reason}

    def search_place(
        self, name: str, aliases: list[str], city: str, country: str = ""
    ) -> dict[str, Any]:
        if normalized_name(city) != normalized_name(self.candidate_city):
            return {"status": "invalid", "results": [], "errors": ["Search city differs from this place"]}
        if (len(name) > 150 or len(city) > 150 or len(country) > 100
                or len(aliases) > 5 or any(len(alias) > 150 for alias in aliases)):
            return {"status": "invalid", "results": [], "errors": ["Search input exceeds configured limits"]}
        names = list(dict.fromkeys(
            part.strip() for part in [name, *aliases[:self.config.max_tool_alias_queries]]
            if part.strip()
        ))
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        if self.wikimedia_client is not None:
            for query in names:
                try:
                    point = self.wikimedia_client.find_place_coordinates(query, disambiguator=city)
                    if point is not None:
                        results.append(self._output(point))
                        break
                except Exception as exc:
                    errors.append(f"Wikipedia: {type(exc).__name__}: {exc}")
        if self.overture_client is not None:
            try:
                candidate = PlaceCandidate(
                    name=name, city=city,
                    aliases=[PlaceAlias(name=alias, source_id="tool-query") for alias in aliases],
                    source_ids=["tool-query"],
                )
                for point in self.overture_client.search_place(
                    candidate, research_location=self.research_location,
                    limit=self.config.max_place_results,
                ):
                    results.append(self._output(point))
            except Exception as exc:
                errors.append(f"Overture: {type(exc).__name__}: {exc}")
        for query in names:
            try:
                for point in self.nominatim_client.search_place(
                    query, city=city, country=country,
                    limit=self.config.max_place_results,
                ):
                    results.append(self._output(point))
            except Exception as exc:
                errors.append(f"Nominatim: {type(exc).__name__}: {exc}")
        unique = {row["candidate_id"]: row for row in results}
        return {"status": "partial_error" if errors else "ok",
                "results": list(unique.values()), "errors": errors}
