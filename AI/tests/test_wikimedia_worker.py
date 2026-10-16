import pytest

from integrations.knowledge.wikimedia.wikimedia_article_provider import WikimediaArticleProvider
from narration.knowledge import InMemoryKnowledgeStore, LocationContext, Scope
from narration.location_discovery.location_context_task import LocationContextTask
from narration.research.contracts import ResearchBudgetExhausted, WikimediaArticle
from narration.research.wikimedia_worker import WikimediaWorker, WikimediaWorkerConfig
from narration.location_discovery.geocoding_models import LocationAddress, NarrationDetailLevel


class FakeGeocoder:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def reverse_geocode(self, lat, lon, language_tag, zoom_level):
        self.calls.append((lat, lon, language_tag, zoom_level))
        return LocationAddress(raw=self.raw)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeWikiSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(next(self.responses))


class FakeArticleClient:
    def __init__(self, articles, sections=None):
        self.articles = articles
        self.sections = sections or {}
        self.calls = []
        self.request_count = 0

    def find_article(self, name, *, disambiguator=""):
        self.calls.append(("find", name, disambiguator))
        self.request_count += 1
        return self.articles.get(name)

    def fetch_sections(self, article):
        self.calls.append(("sections", article.title))
        self.request_count += 1
        return self.sections.get(article.title, "")


def _article(name, lead="A sufficiently long factual introduction about this location."):
    return WikimediaArticle(
        title=name,
        language="pl",
        url=f"https://pl.wikipedia.org/wiki/{name.replace(' ', '_')}",
        lead=lead,
    )


def test_location_context_maps_address_levels_and_region():
    geocoder = FakeGeocoder({"address": {
        "road": "Jedności Narodowej", "neighbourhood": "Nadodrze",
        "city_district": "Śródmieście", "city": "Wrocław",
        "state": "Dolnośląskie", "country": "Polska",
    }})
    context = LocationContextTask(geocoder).run(51.1216, 17.0352)
    assert context.street == "Jedności Narodowej"
    assert context.neighbourhood == "Nadodrze"
    assert context.district == "Śródmieście"
    assert context.city == "Wrocław"
    assert context.region == "Dolnośląskie"
    assert context.country == "Polska"
    assert geocoder.calls == [(51.1216, 17.0352, "pl", NarrationDetailLevel.DETAILED)]


def test_location_context_handles_missing_address_and_validates_coordinates():
    geocoder = FakeGeocoder({})
    context = LocationContextTask(geocoder).run(51.1216, 17.0352)
    assert context.city == ""
    with pytest.raises(ValueError):
        LocationContextTask(geocoder).run(91, 17.0352)
    assert len(geocoder.calls) == 1


def test_provider_reads_short_lead_and_rejects_disambiguation():
    session = FakeWikiSession([
        {"query": {"pages": [{"title": "Nadodrze", "pageprops": {"disambiguation": ""},
                               "extract": "Nadodrze can mean several places."}]}},
        {"query": {"search": [{"title": "Nadodrze (Wrocław)"}]}},
        {"query": {"pages": [{"title": "Nadodrze (Wrocław)",
                               "extract": "Nadodrze is a district in Wrocław."}]}},
    ])
    provider = WikimediaArticleProvider(
        user_agent="TourGuideTest/1.0 (test@example.org)", languages=("pl",), session=session
    )
    article = provider.find_article("Nadodrze", disambiguator="Wrocław")
    assert article.title == "Nadodrze (Wrocław)"
    assert article.url.endswith("Nadodrze_(Wroc%C5%82aw)")
    assert provider.request_count == 3
    assert session.calls[0][1]["params"]["exintro"] == 1
    assert session.calls[0][1]["params"]["exchars"] <= 1200
    assert session.calls[1][1]["params"]["srsearch"] == "Nadodrze Wrocław"


def test_provider_fetches_section_text_and_enforces_request_budget():
    session = FakeWikiSession([{"query": {"pages": [{
        "title": "Wrocław", "extract": "Lead.\n== Historia ==\nLong history section."
    }]}}])
    provider = WikimediaArticleProvider(
        user_agent="TourGuideTest/1.0 (test@example.org)", languages=("pl",),
        max_requests=1, session=session,
    )
    text = provider.fetch_sections(_article("Wrocław"))
    assert "== Historia ==" in text
    assert session.calls[0][1]["params"]["exsectionformat"] == "wiki"
    with pytest.raises(ResearchBudgetExhausted):
        provider.fetch_sections(_article("Wrocław"))
    assert provider.request_count == 1


def test_provider_requires_identifiable_user_agent():
    with pytest.raises(ValueError, match="WIKIMEDIA_USER_AGENT"):
        WikimediaArticleProvider(user_agent="AI-Tour-Guide/0.1 (contact: unavailable)")


def test_worker_falls_back_from_missing_neighbourhood_and_stores_city_sections():
    client = FakeArticleClient(
        {"Wrocław": _article("Wrocław", "Wrocław is a historic city in western Poland.")},
        {"Wrocław": (
            "Wrocław is a historic city in western Poland.\n"
            "== Historia ==\nThe city has a long and well documented history. "
            "This paragraph contains enough detail to form a logical history chunk.\n"
            "== Przypisy ==\nUnrelated reference list that should not become a chunk."
        )},
    )
    store = InMemoryKnowledgeStore()
    callbacks = []
    location = LocationContext(
        lat=51.1216, lon=17.0352, neighbourhood="Nadodrze",
        city="Wrocław", region="Dolnośląskie", country="Polska",
    )
    report = WikimediaWorker(client, store).run(
        location, on_chunk=lambda chunk: callbacks.append((chunk.topic, list(client.calls)))
    )

    assert [attempt.status for attempt in report.attempts] == ["not_found", "found", "not_found", "not_found"]
    assert report.attempts[1].scope is Scope.CITY
    assert report.article_count == 1
    assert report.api_request_count == 5
    assert report.first_chunk_latency_s is not None
    assert report.first_chunk_latency_s <= report.latency_s
    assert len(store.sources) == 1
    assert [chunk.topic for chunk in store.chunks] == ["overview", "history"]
    assert all(chunk.scope is Scope.CITY for chunk in store.chunks)
    assert "Przypisy" not in " ".join(chunk.content for chunk in store.chunks)
    assert callbacks[0][0] == "overview"
    assert ("sections", "Wrocław") not in callbacks[0][1]
    assert "long and well documented history" in store.sources[0].evidence_text


def test_worker_caps_chunks_and_skips_duplicate_area_names():
    client = FakeArticleClient({"Nadodrze": _article("Nadodrze")})
    store = InMemoryKnowledgeStore()
    location = LocationContext(
        lat=51.12, lon=17.03, neighbourhood="Nadodrze", district="Nadodrze",
        city="Wrocław", country="Polska",
    )
    report = WikimediaWorker(
        client, store, WikimediaWorkerConfig(
            max_total_chunks=1, max_chunks_per_article=1, fetch_sections_for_first_n_articles=0,
        )
    ).run(location)
    assert len(report.chunk_ids) == 1
    assert client.calls == [("find", "Nadodrze", "Wrocław")]


def test_worker_returns_empty_report_for_unknown_location():
    client = FakeArticleClient({})
    report = WikimediaWorker(client, InMemoryKnowledgeStore()).run(
        LocationContext(lat=51.12, lon=17.03)
    )
    assert report.api_request_count == 0
    assert report.first_chunk_latency_s is None


def test_region_chunk_is_shared_across_cities_in_same_region():
    store = InMemoryKnowledgeStore()
    client = FakeArticleClient({"Dolnośląskie": _article("Dolnośląskie")})
    worker = WikimediaWorker(client, store, WikimediaWorkerConfig(
        max_total_chunks=1, max_chunks_per_article=1, fetch_sections_for_first_n_articles=0,
    ))
    first = worker.run(LocationContext(
        lat=51.12, lon=17.03, city="Wrocław", region="Dolnośląskie", country="Polska"
    ))
    second = worker.run(LocationContext(
        lat=51.21, lon=16.16, city="Legnica", region="Dolnośląskie", country="Polska"
    ))
    assert first.chunk_ids == second.chunk_ids
    assert len(store.chunks) == 1


def test_district_chunk_is_shared_across_user_positions_in_same_district():
    store = InMemoryKnowledgeStore()
    client = FakeArticleClient({"Nadodrze": _article("Nadodrze")})
    worker = WikimediaWorker(client, store, WikimediaWorkerConfig(
        max_total_chunks=1, max_chunks_per_article=1, fetch_sections_for_first_n_articles=0,
    ))
    first = worker.run(LocationContext(
        lat=51.1216, lon=17.0352, neighbourhood="Nadodrze",
        city="Wrocław", country="Polska",
    ))
    second = worker.run(LocationContext(
        lat=51.1260, lon=17.0310, neighbourhood="Nadodrze",
        city="Wrocław", country="Polska",
    ))
    assert first.chunk_ids == second.chunk_ids
    assert store.chunks[0].scope is Scope.DISTRICT
    assert store.chunks[0].anchor_name == "Nadodrze"
    assert "lat" not in store.chunks[0].model_dump()
    assert len(store.chunks) == 1


def test_stage_two_flow_from_gps_to_sourced_chunk():
    geocoder = FakeGeocoder({"address": {
        "neighbourhood": "Nadodrze", "city": "Wrocław",
        "state": "Dolnośląskie", "country": "Polska",
    }})
    location = LocationContextTask(geocoder).run(51.1216, 17.0352)
    article_client = FakeArticleClient({"Nadodrze": _article("Nadodrze")})
    store = InMemoryKnowledgeStore()
    run = WikimediaWorker(article_client, store, WikimediaWorkerConfig(
        max_total_chunks=1, max_chunks_per_article=1,
        fetch_sections_for_first_n_articles=0,
    )).run(location)

    assert run.first_chunk_latency_s is not None
    assert store.chunks[0].scope is Scope.DISTRICT
    assert store.chunks[0].anchor_name == "Nadodrze"
    assert store.chunks[0].source_ids == [store.sources[0].source_id]
