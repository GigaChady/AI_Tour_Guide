from __future__ import annotations

from narration.information_filtering.information_filtering_task import InformationFilteringTask
from narration.location_discovery.location_discovery_task import LocationDiscoveryTask
from narration.narration_generation.narration_generation_task import NarrationGenerationTask
from narration.poi_enrichment.poi_enrichment_task import PoiEnrichmentTask
from narration.poi_selection.poi_selection_task import PoiSelectionTask
from narration.schemas import NarrationPipelineRequest, TourPipelineResult
from narration.steps import (
    InformationFilteringStep,
    LocationDiscoveryStep,
    NarrationGenerationStep,
    PoiEnrichmentStep,
    PoiSelectionStep,
)


class TourNarrationPipeline:
    def __init__(
        self,
        location_discovery_step: LocationDiscoveryStep,
        poi_selection_step: PoiSelectionStep,
        poi_enrichment_step: PoiEnrichmentStep,
        information_filtering_step: InformationFilteringStep,
        narration_generation_step: NarrationGenerationStep,
    ):
        self.location_discovery_step = location_discovery_step
        self.poi_selection_step = poi_selection_step
        self.poi_enrichment_step = poi_enrichment_step
        self.information_filtering_step = information_filtering_step
        self.narration_generation_step = narration_generation_step

    @classmethod
    def default(
        cls,
        *,
        geocoding_client,
        poi_data_client,
        poi_parser,
        search_client,
        filtering_agent,
        narrative_generation_agent,
        seen_poi_repository=None,
        poi_selection_config=None,
    ) -> "TourNarrationPipeline":
        """Build the standard narration flow from injected provider adapters."""
        return cls(
            location_discovery_step=LocationDiscoveryTask(
                geocoding_client=geocoding_client,
                poi_data_client=poi_data_client,
                poi_parser=poi_parser,
            ),
            poi_selection_step=PoiSelectionTask(
                seen_poi_repository=seen_poi_repository,
                config=poi_selection_config,
            ),
            poi_enrichment_step=PoiEnrichmentTask(search_client=search_client),
            information_filtering_step=InformationFilteringTask(
                filtering_agent=filtering_agent,
            ),
            narration_generation_step=NarrationGenerationTask(
                narrative_generation_agent=narrative_generation_agent,
            ),
        )

    def run(self, request: NarrationPipelineRequest) -> TourPipelineResult:
        settings = request.settings
        discovery = self.location_discovery_step.get_location_details(settings)

        if not settings.include_narration:
            planning_pois = self.poi_selection_step.run_many(
                candidates=discovery.candidates,
                user_latitude=settings.latitude,
                user_longitude=settings.longitude,
                session_id=request.session_id,
            )
            return TourPipelineResult(selected_pois=planning_pois)

        selected = self.poi_selection_step.run(
            candidates=discovery.candidates,
            user_latitude=settings.latitude,
            user_longitude=settings.longitude,
        )
        if selected is None:
            return TourPipelineResult()

        enriched = self.poi_enrichment_step.run(
            selected_poi=selected,
            address=discovery.address,
        )
        filtered = self.information_filtering_step.run(enriched, settings)
        narration = self.narration_generation_step.run(filtered, settings)

        return TourPipelineResult(
            selected_poi=selected,
            enriched_poi=enriched,
            filtered_facts=filtered,
            narration=narration,
        )
