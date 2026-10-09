from narration.information_filtering.information_filtering_task import InformationFilteringTask
from narration.narration_generation.narration_generation_task import NarrationGenerationTask
from narration.poi_enrichment.poi_enrichment_task import PoiEnrichmentTask
from narration.schemas import (
    LocationAddress,
    NarrationDetailLevel,
    NarrationLanguage,
    NarrationSettings,
    PoiCandidate,
    SelectedPoi,
)


class FakeSearchAgent:
    def __init__(self):
        self.query = None

    def search(self, query):
        self.query = query
        return "Search result"


class FailingSearchAgent:
    def search(self, query):
        raise RuntimeError("Body collection error: error decoding response body")


class FakePoiSearchAgent:
    source_type = "wikimedia"

    def __init__(self):
        self.selected_poi = None
        self.address = None

    def search_poi(self, selected_poi, address):
        self.selected_poi = selected_poi
        self.address = address
        return "Wikimedia result"


class FakeFilteringAgent:
    def __init__(self):
        self.enriched_poi = None

    def filter_information(self, enriched_poi, narration_settings):
        self.enriched_poi = enriched_poi
        return f"Facts for {enriched_poi.poi.name}: {enriched_poi.to_context_text()}"


class FakeNarrationAgent:
    def generate_narration(self, location_name, location_info, narration_settings):
        return {
            "location": location_name,
            "narration": f"Narration from {location_info}",
        }


def _settings():
    return NarrationSettings(
        latitude=50.0614,
        longitude=19.9372,
        detail_level=NarrationDetailLevel.DETAILED,
        search_radius=100,
        language=NarrationLanguage(language_name="Polish", language_tag="pl"),
        user_preferences="history",
    )


def test_poi_enrichment_task_builds_query_and_returns_enriched_model():
    search_agent = FakeSearchAgent()
    task = PoiEnrichmentTask(search_client=search_agent)
    selected = SelectedPoi(
        poi=PoiCandidate(
            name="Town Hall Tower",
            category="monument",
            lat=50.0616,
            lon=19.9373,
        ),
        distance_km=0.1,
        category_rank=2,
    )
    address = LocationAddress(
        raw={
            "address": {
                "city": "Krakow",
                "suburb": "Old Town",
                "road": "Florianska",
                "country": "Poland",
            }
        }
    )

    enriched = task.run(selected_poi=selected, address=address)

    assert search_agent.query == (
        '"Town Hall Tower" "Krakow Poland"'
    )
    assert enriched.poi.name == "Town Hall Tower"
    assert enriched.information_sources[0].query == search_agent.query
    assert enriched.information_sources[0].source_type == "web_search"
    assert "Type/category: monument" in enriched.to_context_text()
    assert "Information source 1:\nSearch result" in enriched.to_context_text()
    assert "Coordinates:" not in enriched.to_context_text()


def test_poi_enrichment_task_uses_fallback_context_when_search_fails():
    selected = SelectedPoi(
        poi=PoiCandidate(
            name="Gertraudendenkmal",
            category="memorial",
            lat=52.513,
            lon=13.401,
            description="A local memorial",
        ),
        distance_km=0.12,
        category_rank=2,
    )
    address = LocationAddress(
        raw={
            "address": {
                "city": "Berlin",
                "country": "Germany",
            }
        }
    )

    enriched = PoiEnrichmentTask(search_client=FailingSearchAgent()).run(
        selected_poi=selected,
        address=address,
    )

    assert enriched.poi.name == "Gertraudendenkmal"
    assert "External web search failed" in enriched.information_sources[0].content
    assert "POI category: memorial" in enriched.information_sources[0].content


def test_poi_enrichment_task_uses_poi_aware_search_client_when_available():
    search_agent = FakePoiSearchAgent()
    selected = SelectedPoi(
        poi=PoiCandidate(
            name="Gertraudendenkmal",
            category="memorial",
            lat=52.513,
            lon=13.401,
        ),
        distance_km=0.12,
        category_rank=2,
    )
    address = LocationAddress(raw={"address": {"city": "Berlin", "country": "Germany"}})

    enriched = PoiEnrichmentTask(search_client=search_agent).run(
        selected_poi=selected,
        address=address,
    )

    assert search_agent.selected_poi == selected
    assert search_agent.address == address
    assert enriched.information_sources[0].content == "Wikimedia result"
    assert enriched.information_sources[0].source_type == "wikimedia"


def test_filtering_and_narration_tasks_return_domain_models():
    selected = SelectedPoi(
        poi=PoiCandidate(
            name="Town Hall Tower",
            category="monument",
            lat=50.0616,
            lon=19.9373,
        ),
        distance_km=0.1,
        category_rank=2,
    )
    enriched = PoiEnrichmentTask(search_client=FakeSearchAgent()).run(
        selected_poi=selected,
        address=LocationAddress(),
    )

    filtering_agent = FakeFilteringAgent()
    facts = InformationFilteringTask(filtering_agent=filtering_agent).run(
        enriched,
        _settings(),
    )
    narration = NarrationGenerationTask(
        narrative_generation_agent=FakeNarrationAgent()
    ).run(facts, _settings())

    assert filtering_agent.enriched_poi == enriched
    assert "Facts for Town Hall Tower" in facts.facts
    assert "Type/category: monument" in facts.facts
    assert "Coordinates:" not in facts.facts
    assert narration.location == "Town Hall Tower"
    assert "Facts for Town Hall Tower" in narration.narration
