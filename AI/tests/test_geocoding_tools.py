import json
from types import SimpleNamespace

from integrations.llm.nvidia.config import NvidiaConfig
from integrations.llm.nvidia.nvidia_tool_calling_model import NvidiaToolCallingModel
from narration.knowledge.geocoding_tools import GeocodingToolbox
from narration.knowledge.models import GeocodedPlace, LocationContext, PlaceAlias, PlaceCandidate
from narration.knowledge.store import InMemoryKnowledgeStore
from narration.knowledge.place_location_resolver import PlaceLocationResolver
from narration.knowledge.tool_calling_place_locator import ToolCallingPlaceLocator
from narration.research import TavilyResearchWorker, WebResearchConfig
from narration.research.contracts import WebDocument, WebSearchHit
from narration.research.web_research_worker import _query_plan


LOCATION = LocationContext(lat=51.1216, lon=17.0352, city="Wrocław", country="Polska")
SOURCE = "Kolorowe podwórka przy ul. Roosevelta 14-16 i Roosevelta 5A we Wrocławiu."


def _point(source, name, *, number="", location_type="place"):
    return GeocodedPlace(
        name=name, lat=51.12 + len(number) / 10000, lon=17.035,
        coordinate_source=source, city="Wrocław", country="Polska",
        street="Roosevelta" if number else "", house_number=number,
        location_type=location_type,
    )


class AddressSearch:
    def __init__(self):
        self.numbers = []

    def search_address(self, address, *, country=""):
        self.numbers.append(address.house_number)
        return [_point(f"gus_address:{address.house_number}",
                       f"Roosevelta {address.house_number}",
                       number=address.house_number, location_type="address")]


class PlaceSearch:
    def __init__(self):
        self.queries = []

    def search_place(self, name, *, city, country="", limit=5):
        self.queries.append(name)
        return [_point(f"nominatim:{len(self.queries)}", "Wrocław Nadodrze")]


class OvertureSearch:
    def search_place(self, candidate, *, research_location, limit=5):
        return [_point("overture:1", "Wrocław Nadodrze")]


class WikipediaSearch:
    def find_place_coordinates(self, name, *, disambiguator=""):
        return _point("wikipedia:1", "Wrocław Nadodrze")


def test_address_tool_returns_each_point_of_sourced_range():
    address = AddressSearch()
    toolbox = GeocodingToolbox(
        address_client=address, overture_client=None,
        nominatim_client=PlaceSearch(), wikimedia_client=None,
        research_location=LOCATION, source_text=SOURCE, candidate_city="Wrocław",
    )
    result = toolbox.invoke("geocode_address", {
        "address": "Roosevelta 14-16", "city": "Wrocław", "country": "Polska",
    })
    assert result["status"] == "ok"
    assert address.numbers == ["14", "15", "16"]
    assert [row["candidate_id"] for row in result["results"]] == ["geo_1", "geo_2", "geo_3"]
    assert [row["house_number"] for row in result["results"]] == ["14", "15", "16"]
    assert toolbox.geocode_address("Roosevelta 100-200", "Wrocław", "Polska")["status"] == "invalid"
    assert toolbox.geocode_address("Nieznana 5", "Wrocław", "Polska")["status"] == "invalid"


def test_search_tool_keeps_candidates_from_all_sources_and_searches_alias():
    nominatim = PlaceSearch()
    toolbox = GeocodingToolbox(
        address_client=None, overture_client=OvertureSearch(),
        nominatim_client=nominatim, wikimedia_client=WikipediaSearch(),
        research_location=LOCATION, source_text=SOURCE, candidate_city="Wrocław",
    )
    result = toolbox.search_place(
        "Wrocław Nadodrze (railway station)", ["dworzec Wrocław Nadodrze"],
        "Wrocław", "Polska",
    )
    assert result["status"] == "ok"
    assert len(result["results"]) == 4
    assert nominatim.queries == ["Wrocław Nadodrze (railway station)",
                                 "dworzec Wrocław Nadodrze"]
    assert {row["coordinate_source"] for row in result["results"]} == {
        "wikipedia:1", "overture:1", "nominatim:1", "nominatim:2",
    }


def test_search_tool_reports_catalogue_failure_separately_from_no_results():
    class BrokenOverture:
        def search_place(self, *args, **kwargs):
            raise RuntimeError("service unavailable")

    class EmptyNominatim:
        def search_place(self, *args, **kwargs):
            return []

    toolbox = GeocodingToolbox(
        address_client=None, overture_client=BrokenOverture(),
        nominatim_client=EmptyNominatim(), wikimedia_client=None,
        research_location=LOCATION, source_text=SOURCE, candidate_city="Wrocław",
    )
    result = toolbox.search_place("Park Słowiański", [], "Wrocław", "Polska")
    assert result["status"] == "partial_error"
    assert result["results"] == []
    assert any("Overture" in error for error in result["errors"])


class ScriptedModel:
    def __init__(self, ids):
        self.ids = ids
        self.messages = []

    def create(self, messages, *, tools, tool_choice="auto"):
        self.messages.append(messages)
        if len(self.messages) == 1:
            assert {tool["function"]["name"] for tool in tools} == {
                "geocode_address", "search_place",
            }
            return {"content": None, "tool_calls": [{
                "id": "call_1", "type": "function", "function": {
                    "name": "geocode_address",
                    "arguments": json.dumps({"address": "Roosevelta 14-16",
                                             "city": "Wrocław", "country": "Polska"}),
                },
            }]}
        return {"content": json.dumps({
            "selected_candidate_ids": self.ids,
            "representative_candidate_id": self.ids[0],
            "reason": "Several sourced courtyards belong to this place",
        })}


def test_model_selects_multiple_returned_address_points():
    model = ScriptedModel(["geo_1", "geo_3"])
    resolver = PlaceLocationResolver(PlaceSearch(), address_client=AddressSearch())
    locator = ToolCallingPlaceLocator(model, resolver)
    candidate = PlaceCandidate(name="Kolorowe podwórka", city="Wrocław",
                               source_ids=["source:1"])
    notes, calls = [], []
    selected = locator.resolve(
        candidate, source_url="", source_text=SOURCE, research_location=LOCATION,
        description="Courtyards at Roosevelt 14-16", diagnostics=notes,
        model_calls=calls,
    )
    assert calls == [1, 1]
    assert selected.coordinate_source == "gus_address:14"
    assert [point.house_number for point in selected.locations] == ["14", "16"]
    assert selected.external_ids == {}
    assert any("Model selected 2 point" in note for note in notes)
    assert any(message["role"] == "tool" for message in model.messages[1])


def test_model_cannot_select_unknown_candidate_id():
    locator = ToolCallingPlaceLocator(
        ScriptedModel(["geo_999"]),
        PlaceLocationResolver(PlaceSearch(), address_client=AddressSearch()),
    )
    notes = []
    assert locator.resolve(
        PlaceCandidate(name="Kolorowe podwórka", city="Wrocław", source_ids=["source:1"]),
        source_url="", source_text=SOURCE, research_location=LOCATION,
        diagnostics=notes,
    ) is None
    assert "Model selected an unknown candidate ID" in notes


def test_nvidia_tool_model_sends_tool_schema_and_returns_message():
    class Session:
        def post(self, url, **kwargs):
            self.url, self.kwargs = url, kwargs
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"choices": [{"message": {"tool_calls": []}}]},
            )
    session = Session()
    model = NvidiaToolCallingModel(
        NvidiaConfig(model_name="z-ai/glm-5.3-flash"),
        api_key="test-key", session=session,
    )
    assert model.create([{"role": "user", "content": "Find place"}],
                        tools=GeocodingToolbox.schemas()) == {"tool_calls": []}
    assert session.kwargs["json"]["model"] == "z-ai/glm-5.3-flash"
    assert len(session.kwargs["json"]["tools"]) == 2
    model_with_template = NvidiaToolCallingModel(
        NvidiaConfig(model_name="z-ai/glm-5.3-flash", reasoning_effort="low"),
        api_key="test-key", session=session,
        chat_template_kwargs={"reasoning_effort": "low", "clear_thinking": True},
    )
    model_with_template.create([{"role": "user", "content": "Find place"}],
                               tools=GeocodingToolbox.schemas())
    assert session.kwargs["json"]["chat_template_kwargs"]["clear_thinking"] is True
    assert "reasoning_effort" not in session.kwargs["json"]


def test_tavily_worker_uses_new_locator_when_enabled():
    class Client:
        request_count = 0

        def search(self, query, *, max_results):
            self.request_count += 1
            return [WebSearchHit("Kolorowe podwórka", "https://example.org/place",
                                 "Kolorowe podwórka we Wrocławiu", query)] if query == first_query else []

        def extract(self, hit, *, max_chars):
            self.request_count += 1
            return WebDocument(hit.title, hit.url, SOURCE)

    class ExtractionModel:
        def generate(self, messages):
            return json.dumps({"items": [{
                "scope": "PLACE", "anchor_name": "Kolorowe podwórka",
                "topic": "Community art",
                "content": "Colourful courtyards on Roosevelt Street were made with local residents and artists.",
                "city": "Wrocław", "address": "Roosevelta 14-16",
            }]})

    class OldLocator:
        def resolve(self, *args, **kwargs):
            raise AssertionError("Old locator should stay unused when tool locator is enabled")

    class NewLocator:
        def resolve(self, candidate, *, model_calls, **kwargs):
            model_calls.extend([1, 1])
            return PlaceCandidate.model_validate({
                **candidate.model_dump(), "lat": 51.12, "lon": 17.035,
                "coordinate_source": "gus_address:14",
                "locations": [_point("gus_address:14", "Roosevelta 14",
                                     number="14", location_type="address")],
            })

    first_query = _query_plan(LOCATION)[0]
    store = InMemoryKnowledgeStore()
    report = TavilyResearchWorker(
        Client(), ExtractionModel(), store,
        WebResearchConfig(max_search_calls=1, max_extract_attempts=1,
                          max_successful_documents=1),
        place_locator=OldLocator(), tool_place_locator=NewLocator(),
    ).run(LOCATION)
    assert report.llm_calls == 3
    assert len(store.places) == len(report.place_ids) == len(report.chunk_ids) == 1
    assert store.places[0].locations[0].house_number == "14"
