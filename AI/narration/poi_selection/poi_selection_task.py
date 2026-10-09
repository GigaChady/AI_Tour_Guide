from __future__ import annotations

import logging
from math import asin, cos, radians, sin, sqrt

from narration.poi_selection.config import PoiSelectionConfig
from narration.poi_selection.contracts import SeenPoiRepository
from narration.schemas import PoiCandidate, SelectedPoi

logger = logging.getLogger(__name__)


class PoiSelectionTask:
    def __init__(
        self,
        seen_poi_repository: SeenPoiRepository | None = None,
        config: PoiSelectionConfig | None = None,
    ):
        self.seen_poi_repository = seen_poi_repository
        self.config = config or PoiSelectionConfig()

    def run(
        self,
        candidates: list[PoiCandidate],
        user_latitude: float,
        user_longitude: float,
        session_id: str | None = None,
    ) -> SelectedPoi | None:
        if not candidates:
            return None

        pool = self._selection_pool(candidates, session_id)
        ranked = self._rank(pool, user_latitude, user_longitude)
        selected = ranked[0]
        result = self._to_selected(selected, user_latitude, user_longitude)
        self._mark_seen(session_id, selected.name)

        logger.info(
            "Selected POI: %s, category: %s, distance: %.2fkm, score: %.2f",
            selected.name,
            selected.category,
            result.distance_km,
            self._selection_score(selected, user_latitude, user_longitude),
        )
        return result

    def run_many(
        self,
        candidates: list[PoiCandidate],
        user_latitude: float,
        user_longitude: float,
        session_id: str | None = None,
        n: int | None = None,
    ) -> list[SelectedPoi]:
        if not candidates:
            return []

        limit = n or self.config.planning_result_limit
        pool = self._selection_pool(candidates, session_id)
        ranked = self._rank(pool, user_latitude, user_longitude)
        results = []
        for poi in ranked[:limit]:
            results.append(self._to_selected(poi, user_latitude, user_longitude))
            self._mark_seen(session_id, poi.name)

        logger.info("Selected %d POIs for planning mode", len(results))
        return results

    def _selection_pool(
        self,
        candidates: list[PoiCandidate],
        session_id: str | None,
    ) -> list[PoiCandidate]:
        unseen = self._filter_seen(candidates, session_id)
        return unseen if unseen else candidates

    def _rank(
        self,
        candidates: list[PoiCandidate],
        user_latitude: float,
        user_longitude: float,
    ) -> list[PoiCandidate]:
        return sorted(
            candidates,
            key=lambda poi: self._selection_score(
                poi,
                user_latitude,
                user_longitude,
            ),
        )

    def _to_selected(
        self,
        poi: PoiCandidate,
        user_latitude: float,
        user_longitude: float,
    ) -> SelectedPoi:
        return SelectedPoi(
            poi=poi,
            distance_km=self._haversine_distance(
                user_latitude,
                user_longitude,
                poi.lat,
                poi.lon,
            ),
            category_rank=self.config.category_ranks.get(
                poi.category,
                self.config.default_category_rank,
            ),
        )

    def _filter_seen(
        self,
        candidates: list[PoiCandidate],
        session_id: str | None,
    ) -> list[PoiCandidate]:
        if self.seen_poi_repository is None or session_id is None:
            return candidates
        try:
            seen = self.seen_poi_repository.get_seen(session_id)
            return [candidate for candidate in candidates if self._key(candidate.name) not in seen]
        except Exception:
            logger.warning("Seen POI lookup failed; skipping deduplication")
            return candidates

    def _mark_seen(self, session_id: str | None, name: str) -> None:
        if self.seen_poi_repository is None or session_id is None:
            return
        try:
            self.seen_poi_repository.mark_seen(session_id, self._key(name))
        except Exception:
            logger.warning("POI '%s' could not be marked as seen", name)

    def _selection_score(
        self,
        poi: PoiCandidate,
        user_latitude: float,
        user_longitude: float,
    ) -> float:
        distance = self._haversine_distance(
            user_latitude,
            user_longitude,
            poi.lat,
            poi.lon,
        )
        category_penalty = self.config.category_ranks.get(
            poi.category,
            self.config.default_category_rank,
        )
        return (
            distance * self.config.distance_weight
            + category_penalty
            - self._popularity_bonus(poi)
        )

    def _popularity_bonus(self, poi: PoiCandidate) -> float:
        bonus = 0.0
        if poi.wikipedia:
            bonus += self.config.wikipedia_bonus
        if poi.wikidata:
            bonus += self.config.wikidata_bonus
        if poi.website:
            bonus += self.config.website_bonus
        if poi.description:
            bonus += self.config.description_bonus
        return bonus

    @staticmethod
    def _key(name: str) -> str:
        return name.strip().lower()

    @staticmethod
    def _haversine_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 6371 * 2 * asin(sqrt(value))
