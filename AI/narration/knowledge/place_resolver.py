from __future__ import annotations

import math
from dataclasses import dataclass, field

from narration.knowledge.models import Place, PlaceCandidate
from narration.knowledge.normalization import normalized_name, normalized_street


@dataclass(frozen=True)
class MatchDecision:
    place_id: str | None = None
    reason: str = "new_place"
    possible_match_ids: list[str] = field(default_factory=list)


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    first_lat, second_lat = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * 6_371_000 * math.asin(min(1.0, math.sqrt(value)))


class PlaceResolver:
    """Conservative, deterministic resolution of concrete PLACE entities."""

    def __init__(
        self,
        *,
        name_distance_m: float = 150,
        id_conflict_distance_m: float = 300,
        proximity_review_m: float = 30,
    ):
        if (
            name_distance_m <= 0
            or id_conflict_distance_m < name_distance_m
            or not 0 < proximity_review_m <= name_distance_m
        ):
            raise ValueError("invalid place distance thresholds")
        self.name_distance_m = name_distance_m
        self.id_conflict_distance_m = id_conflict_distance_m
        self.proximity_review_m = proximity_review_m

    def resolve(self, candidate: PlaceCandidate, places: list[Place]) -> MatchDecision:
        strong: list[tuple[str, str]] = []
        possible: list[str] = []

        candidate_names = {
            normalized_name(candidate.name),
            *(normalized_name(alias.name) for alias in candidate.aliases),
        }
        for place in places:
            existing_names = {
                normalized_name(place.canonical_name),
                *(normalized_name(alias.name) for alias in place.aliases),
            }
            name_matches = bool(candidate_names & existing_names)
            shared_id_types = candidate.external_ids.keys() & place.external_ids.keys()
            ids_conflict = any(
                candidate.external_ids[key].casefold() != place.external_ids[key].casefold()
                for key in shared_id_types
            )
            candidate_location_ids = {point.coordinate_source for point in candidate.locations}
            place_location_ids = {point.coordinate_source for point in place.locations}
            shared_location = bool(candidate_location_ids & place_location_ids)
            id_matches = (bool(shared_id_types) or shared_location) and not ids_conflict
            city_matches = normalized_name(candidate.city) == normalized_name(place.city)
            candidate_points = [(point.lat, point.lon) for point in candidate.locations]
            place_points = [(point.lat, point.lon) for point in place.locations]
            if candidate.lat is not None:
                candidate_points.append((candidate.lat, candidate.lon))
            if place.lat is not None:
                place_points.append((place.lat, place.lon))
            has_both_coordinates = bool(candidate_points and place_points)
            distance = (
                min(_distance_m(*left, *right)
                    for left in candidate_points for right in place_points)
                if has_both_coordinates
                else None
            )

            if ids_conflict:
                continue
            if id_matches:
                if city_matches and (distance is None or distance <= self.id_conflict_distance_m):
                    strong.append((place.place_id, "matching_external_id"))
                else:
                    possible.append(place.place_id)
                continue
            if not city_matches:
                continue
            if name_matches and distance is not None and distance <= self.name_distance_m:
                strong.append((place.place_id, "name_or_alias_and_coordinates"))
            elif (
                name_matches
                and distance is None
                and candidate.street
                and place.street
                and normalized_street(candidate.street) == normalized_street(place.street)
            ):
                strong.append((place.place_id, "name_or_alias_and_street"))
            elif name_matches and (distance is None or distance <= self.id_conflict_distance_m):
                possible.append(place.place_id)
            elif distance is not None and distance <= self.proximity_review_m:
                possible.append(place.place_id)

        if len(strong) == 1:
            place_id, reason = strong[0]
            return MatchDecision(place_id=place_id, reason=reason)
        if len(strong) > 1:
            possible.extend(place_id for place_id, _ in strong)
        if possible:
            return MatchDecision(
                reason="ambiguous_place",
                possible_match_ids=sorted(set(possible)),
            )
        return MatchDecision()
