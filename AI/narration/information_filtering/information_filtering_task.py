from __future__ import annotations

from narration.information_filtering.contracts import InformationFilteringAgent
from narration.schemas import EnrichedPoi, FilteredPoiFacts, NarrationSettings


class InformationFilteringTask:
    def __init__(self, filtering_agent: InformationFilteringAgent):
        self.filtering_agent = filtering_agent

    def run(
        self,
        enriched_poi: EnrichedPoi,
        narration_settings: NarrationSettings,
    ) -> FilteredPoiFacts:
        return FilteredPoiFacts(
            poi=enriched_poi.poi,
            facts=self.filtering_agent.filter_information(
                enriched_poi,
                narration_settings,
            ),
        )
