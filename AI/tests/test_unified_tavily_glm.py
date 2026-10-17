import json

from experiments.unified_tavily_glm import UnifiedTavilyGlmExperiment
from narration.knowledge.models import GeocodedPlace, LocationContext
from narration.knowledge.place_location_resolver import PlaceLocationResolver
from narration.knowledge.store import InMemoryKnowledgeStore
from narration.research.contracts import WebDocument


LOCATION = LocationContext(lat=51.12, lon=17.04, city="Wrocław", country="Polska")
DOCUMENTS = [WebDocument("Nadodrze", "https://example.org/nadodrze",
                         "Park Staszica and Park Słowiański are in Wrocław.")]


class PlaceSearch:
    def search_place(self, name, *, city, country="", limit=5):
        longitude = 17.03 if name == "Park Staszica" else 17.04
        return [GeocodedPlace(
            name=name, lat=51.12, lon=longitude,
            coordinate_source=f"nominatim:{name}", city=city, country="Polska",
        )]


class BatchModel:
    def __init__(self, *, invalid_id=False):
        self.messages = []
        self.invalid_id = invalid_id

    def create(self, messages, *, tools, tool_choice="auto"):
        self.messages.append([dict(message) for message in messages])
        if len(self.messages) == 1:
            assert "RESEARCH TEXT:" in messages[1]["content"]
            assert {tool["function"]["name"] for tool in tools} == {
                "geocode_address", "search_place",
            }
            return {"content": None, "tool_calls": [
                {"id": f"call_{index}", "type": "function", "function": {
                    "name": "search_place", "arguments": json.dumps({
                        "name": name, "aliases": [], "city": "Wrocław", "country": "Polska",
                    }),
                }}
                for index, name in enumerate(("Park Staszica", "Park Słowiański"), 1)
            ]}
        tool_results = [json.loads(message["content"]) for message in messages
                        if message["role"] == "tool"]
        assert len(tool_results) == 2
        ids = [result["results"][0]["candidate_id"] for result in tool_results]
        if self.invalid_id:
            ids[0] = "geo_999"
        return {"content": json.dumps({"items": [
            {"scope": "PLACE", "anchor_name": name, "topic": "Park history",
             "content": f"{name} is a named park in the Nadodrze district of Wrocław.",
             "city": "Wrocław", "selected_candidate_ids": [identifier],
             "representative_candidate_id": identifier}
            for name, identifier in zip(("Park Staszica", "Park Słowiański"), ids)
        ]})}


def test_glm_can_request_multiple_tools_and_return_complete_batch():
    model = BatchModel()
    store = InMemoryKnowledgeStore()
    report = UnifiedTavilyGlmExperiment(
        model, PlaceLocationResolver(PlaceSearch()),
    ).run(LOCATION, DOCUMENTS, store)

    assert report.errors == []
    assert report.model_calls == 2
    assert report.tool_calls == 2
    assert len(report.place_ids) == 2
    assert len(report.chunk_ids) == 2
    assert {place.coordinate_source for place in store.places} == {
        "nominatim:Park Staszica", "nominatim:Park Słowiański",
    }
    assert all(chunk.source_urls == [DOCUMENTS[0].url] for chunk in store.chunks)


def test_glm_cannot_save_unreturned_candidate_id():
    store = InMemoryKnowledgeStore()
    report = UnifiedTavilyGlmExperiment(
        BatchModel(invalid_id=True), PlaceLocationResolver(PlaceSearch()),
    ).run(LOCATION, DOCUMENTS, store)

    assert report.model_calls == 2
    assert report.unresolved_places == ["Park Staszica"]
    assert len(store.places) == 1
    assert len(store.chunks) == 1
