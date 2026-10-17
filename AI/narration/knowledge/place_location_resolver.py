from __future__ import annotations

import math
from typing import Protocol
from urllib.parse import urlsplit

from narration.knowledge.models import GeocodedPlace, LocationContext, PlaceCandidate
from narration.knowledge.address_evidence import (
    SupportedAddress, normalized_address_street, supported_address,
)
from narration.knowledge.normalization import normalized_name
from narration.knowledge.place_location_config import PlaceLocationConfig


class PlaceSearchClient(Protocol):
    def search_place(
        self, name: str, *, city: str, country: str = "", limit: int = 5
    ) -> list[GeocodedPlace]: ...


class WikimediaPlaceClient(Protocol):
    def find_place_coordinates(
        self, name: str, *, disambiguator: str = ""
    ) -> GeocodedPlace | None: ...


class AddressSearchClient(Protocol):
    def search_address(
        self, address: SupportedAddress, *, country: str = ""
    ) -> list[GeocodedPlace]: ...


class OverturePlaceClient(Protocol):
    def search_place(
        self, candidate: PlaceCandidate, *, research_location: LocationContext,
        limit: int = 5,
    ) -> list[GeocodedPlace]: ...


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * 6_371_000 * math.asin(min(1.0, math.sqrt(value)))


def _name_score(candidate: PlaceCandidate, result: GeocodedPlace) -> int:
    sought = {normalized_name(candidate.name)} | {
        normalized_name(alias.name) for alias in candidate.aliases
    }
    found = {normalized_name(result.name)} | {
        normalized_name(alias) for alias in result.aliases
    }
    if any(name and name in found for name in sought):
        return 2
    # Permit a shortened name such as "Mosty Chrobrego" for
    # "Mosty Bolesława Chrobrego", but not a different object type.
    for name in sought:
        for option in found:
            left, right = name.split(), option.split()
            if (
                left and right and left[0] == right[0]
                and len(set(left) & set(right)) >= 2
                and len(set(left) & set(right)) / max(len(set(left)), len(set(right))) >= 2 / 3
            ):
                return 1
    return 0


class PlaceLocationResolver:
    """Locate a source-backed PLACE independently of the current user."""

    def __init__(
        self,
        search_client: PlaceSearchClient,
        wikimedia_client: WikimediaPlaceClient | None = None,
        *,
        address_client: AddressSearchClient | None = None,
        overture_client: OverturePlaceClient | None = None,
        config: PlaceLocationConfig | None = None,
    ):
        self.search_client = search_client
        self.wikimedia_client = wikimedia_client
        self.address_client = address_client
        self.overture_client = overture_client
        self.config = config or PlaceLocationConfig()
        self._cache: dict[tuple[str, str, str], list[GeocodedPlace]] = {}

    def resolve(
        self,
        candidate: PlaceCandidate,
        *,
        source_url: str,
        source_text: str,
        research_location: LocationContext,
        diagnostics: list[str] | None = None,
    ) -> PlaceCandidate | None:
        if candidate.lat is not None:
            return candidate

        notes: list[str] = []
        if candidate.address:
            address, reason = supported_address(
                candidate.address, city=candidate.city, source_text=source_text,
                max_chars=self.config.max_address_chars,
            )
            if address is None:
                notes.append(f"Address ignored: {reason}")
                candidate = candidate.model_copy(update={"address": ""})
            elif self.address_client is None:
                notes.append("Address geocoder is not configured")
            else:
                try:
                    found = self.address_client.search_address(
                        address, country=research_location.country
                    )
                    valid = [point for point in found if (
                        normalized_name(point.city) == normalized_name(candidate.city)
                        and normalized_name(point.house_number) == normalized_name(address.house_number)
                        and normalized_address_street(point.street) == normalized_address_street(address.street)
                        and point.location_type == "address"
                    )]
                    distinct = {point.coordinate_source: point for point in valid}
                    notes.append(f"Address geocoder returned {len(distinct)} exact points")
                    if len(distinct) == 1:
                        point = next(iter(distinct.values()))
                        if diagnostics is not None:
                            diagnostics.extend(notes)
                        return self._enrich(candidate, point, [point])
                    if len(distinct) > 1:
                        notes.append("Address is ambiguous; trying place catalogues")
                except Exception as exc:
                    notes.append(f"Address lookup failed: {type(exc).__name__}: {exc}")

        host = (urlsplit(source_url).hostname or "").casefold()
        if self.wikimedia_client and host.endswith(".wikipedia.org"):
            try:
                wiki = self.wikimedia_client.find_place_coordinates(
                    candidate.name, disambiguator=candidate.city
                )
            except Exception as exc:
                wiki = None
                notes.append(f"Wikipedia lookup failed: {type(exc).__name__}: {exc}")
            if wiki is not None:
                if diagnostics is not None:
                    diagnostics.extend(notes)
                    diagnostics.append("Wikipedia article coordinates selected")
                return self._enrich(candidate, wiki, [wiki])
            if not notes:
                notes.append("Wikipedia returned no supported coordinates")

        if self.overture_client is not None:
            if normalized_name(candidate.city) != normalized_name(research_location.city):
                notes.append("Overture skipped: place is outside the loaded research city")
            else:
                try:
                    overture = self.overture_client.search_place(
                        candidate, research_location=research_location,
                        limit=self.config.max_place_results,
                    )
                    overture_choices, _ = self._matching_results(candidate, overture, research_location)
                    notes.append(f"Overture returned {len(overture)} results, {len(overture_choices)} matching")
                    if overture_choices:
                        ordered = sorted(overture_choices, key=lambda row: (-row[0], row[1]))
                        unique = {row[2].coordinate_source: row[2] for row in overture_choices}
                        if diagnostics is not None:
                            diagnostics.extend(notes)
                        return self._enrich(candidate, ordered[0][2], list(unique.values()))
                except Exception as exc:
                    notes.append(f"Overture lookup failed: {type(exc).__name__}: {exc}")

        results = self._search(candidate.name, candidate.city, research_location.country)
        notes.append(f"Nominatim returned {len(results)} results for primary name")
        if not results and candidate.aliases:
            results = self._search(
                candidate.aliases[0].name, candidate.city, research_location.country
            )
            notes.append(f"Nominatim returned {len(results)} results for first alias")

        choices, rejected = self._matching_results(candidate, results, research_location)
        if not choices:
            if diagnostics is not None:
                diagnostics.extend(notes)
                diagnostics.append(
                    "Rejected Nominatim results: "
                    + ", ".join(f"{reason}={count}" for reason, count in rejected.items())
                )
                if results and candidate.aliases:
                    diagnostics.append("Alias lookup skipped because primary search returned results")
            return None
        ordered = sorted(choices, key=lambda row: (-row[0], row[1]))
        unique = {row[2].coordinate_source: row[2] for row in choices}
        if diagnostics is not None:
            diagnostics.extend(notes)
        return self._enrich(candidate, ordered[0][2], list(unique.values()))

    @staticmethod
    def _matching_results(
        candidate: PlaceCandidate, results: list[GeocodedPlace],
        research_location: LocationContext,
    ) -> tuple[list[tuple[int, float, GeocodedPlace]], dict[str, int]]:
        choices: list[tuple[int, float, GeocodedPlace]] = []
        rejected = {"name": 0, "city": 0, "country": 0}
        for result in results:
            name_score = _name_score(candidate, result)
            if not name_score:
                rejected["name"] += 1
                continue
            if not result.city or normalized_name(result.city) != normalized_name(candidate.city):
                rejected["city"] += 1
                continue
            if (research_location.country and result.country
                    and normalized_name(result.country) != normalized_name(research_location.country)):
                rejected["country"] += 1
                continue
            distance = _distance_m(
                research_location.lat, research_location.lon, result.lat, result.lon
            )
            choices.append((name_score, distance, result))
        return choices, rejected

    def _search(self, name: str, city: str, country: str) -> list[GeocodedPlace]:
        key = (normalized_name(name), normalized_name(city), normalized_name(country))
        if key not in self._cache:
            self._cache[key] = self.search_client.search_place(
                name, city=city, country=country, limit=self.config.max_place_results
            )
        return self._cache[key]

    @staticmethod
    def _enrich(
        candidate: PlaceCandidate, result: GeocodedPlace, locations: list[GeocodedPlace]
    ) -> PlaceCandidate:
        # A Place can have several OSM objects, so its scalar external_ids
        # cannot represent a single selected OSM object as the whole place.
        primary_ids = (
            result.external_ids
            if result.location_type == "place"
            and not result.coordinate_source.startswith("nominatim:")
            else {}
        )
        return PlaceCandidate.model_validate({
            **candidate.model_dump(),
            "city": result.city or candidate.city,
            "street": candidate.street or result.street,
            "lat": result.lat,
            "lon": result.lon,
            "coordinate_source": result.coordinate_source,
            "external_ids": {**candidate.external_ids, **primary_ids},
            "locations": [*candidate.locations, *locations],
        })
