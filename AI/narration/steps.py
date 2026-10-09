from __future__ import annotations

from typing import Protocol

from narration.schemas import (
    EnrichedPoi,
    FilteredPoiFacts,
    LocationAddress,
    LocationDiscoveryResult,
    NarrationResult,
    NarrationSettings,
    PoiCandidate,
    SelectedPoi,
)


class LocationDiscoveryStep(Protocol):
    def get_location_details(
        self,
        narration_settings: NarrationSettings,
    ) -> LocationDiscoveryResult: ...


class PoiSelectionStep(Protocol):
    def run(
        self,
        candidates: list[PoiCandidate],
        user_latitude: float,
        user_longitude: float,
        session_id: str | None = None,
    ) -> SelectedPoi | None: ...

    def run_many(
        self,
        candidates: list[PoiCandidate],
        user_latitude: float,
        user_longitude: float,
        session_id: str | None = None,
        n: int | None = None,
    ) -> list[SelectedPoi]: ...


class PoiEnrichmentStep(Protocol):
    def run(
        self,
        selected_poi: SelectedPoi,
        address: LocationAddress,
    ) -> EnrichedPoi: ...


class InformationFilteringStep(Protocol):
    def run(
        self,
        enriched_poi: EnrichedPoi,
        narration_settings: NarrationSettings,
    ) -> FilteredPoiFacts: ...


class NarrationGenerationStep(Protocol):
    def run(
        self,
        filtered_facts: FilteredPoiFacts,
        narration_settings: NarrationSettings,
    ) -> NarrationResult: ...
