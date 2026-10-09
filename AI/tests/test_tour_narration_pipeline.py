from narration.information_filtering.information_filtering_task import InformationFilteringTask
from narration.narration_generation.narration_generation_task import NarrationGenerationTask
from narration.pipeline import TourNarrationPipeline
from narration.poi_enrichment.poi_enrichment_task import PoiEnrichmentTask
from narration.poi_selection.poi_selection_task import PoiSelectionTask
from narration.schemas import (
    LocationAddress,
    LocationDiscoveryResult,
    NarrationDetailLevel,
    NarrationLanguage,
    NarrationPipelineRequest,
    NarrationSettings,
    PoiCandidate,
)


class FakeLocationDiscoveryStep:
    def get_location_details(self, narration_settings):
        return LocationDiscoveryResult(
            address=LocationAddress(
                raw={
                    "address": {
                        "city": "Krakow",
                        "suburb": "Old Town",
                        "road": "Florianska",
                        "country": "Poland",
                    }
                }
            ),
            candidates=[
                PoiCandidate(
                    name="Town Hall Tower",
                    category="monument",
                    lat=50.0616,
                    lon=19.9373,
                    description="Historic tower",
                )
            ],
        )


class FakeSearchClient:
    def __init__(self):
        self.query = None

    def search(self, query):
        self.query = query
        return "Raw historical information"


class FakeFilteringAgent:
    def filter_information(self, enriched_poi, narration_settings):
        return f"Filtered facts about {enriched_poi.poi.name}: {enriched_poi.to_context_text()}"


class FakeNarrativeGenerationAgent:
    def generate_narration(
        self,
        location_name: str,
        location_info: str,
        narration_settings,
    ):
        return {
            "location": location_name,
            "narration": f"Narration based on {location_info}",
        }


def _pipeline(include_narration=True, search_client=None):
    pipeline = TourNarrationPipeline(
        location_discovery_step=FakeLocationDiscoveryStep(),
        poi_selection_step=PoiSelectionTask(),
        poi_enrichment_step=PoiEnrichmentTask(
            search_client=search_client or FakeSearchClient()
        ),
        information_filtering_step=InformationFilteringTask(
            filtering_agent=FakeFilteringAgent()
        ),
        narration_generation_step=NarrationGenerationTask(
            narrative_generation_agent=FakeNarrativeGenerationAgent()
        ),
    )
    request = NarrationPipelineRequest(
        session_id="session-1",
        settings=_settings(include_narration=include_narration),
    )
    return pipeline, request


def _settings(include_narration=True):
    return NarrationSettings(
        latitude=50.0614,
        longitude=19.9372,
        detail_level=NarrationDetailLevel.DETAILED,
        search_radius=100,
        language=NarrationLanguage(language_name="Polish", language_tag="pl"),
        user_preferences="history",
        include_narration=include_narration,
    )


def test_pipeline_runs_all_steps_and_returns_narration():
    search_client = FakeSearchClient()
    pipeline, request = _pipeline(search_client=search_client)

    result = pipeline.run(request)

    assert result.poi is not None
    assert result.poi.name == "Town Hall Tower"
    assert result.enriched_poi is not None
    assert result.enriched_poi.information_sources[0].query == search_client.query
    assert "Type/category: monument" in result.enriched_poi.to_context_text()
    assert "Information source 1:\nRaw historical information" in result.enriched_poi.to_context_text()
    assert "Coordinates:" not in result.enriched_poi.to_context_text()
    assert result.filtered_facts is not None
    assert "Filtered facts" in result.filtered_facts.facts
    assert result.narration is not None
    assert result.narration.location == "Town Hall Tower"
    assert search_client.query == (
        '"Town Hall Tower" "Krakow Poland"'
    )


def test_pipeline_skips_narration_when_disabled():
    pipeline, request = _pipeline(include_narration=False)

    result = pipeline.run(request)

    assert len(result.selected_pois) == 1
    assert result.selected_pois[0].poi.name == "Town Hall Tower"
    assert result.enriched_poi is None
    assert result.filtered_facts is None
    assert result.narration is None
