import json

import pytest

from integrations.knowledge.tavily import TavilyResearchClient
from integrations.knowledge.tavily.markdown_cleanup import clean_extracted_markdown
from narration.knowledge import (
    GeocodedPlace,
    InMemoryKnowledgeStore,
    LocationContext,
    PlaceCandidate,
    PlaceLocationResolver,
    Scope,
    Source,
)
from narration.research import TavilyResearchWorker, WebResearchConfig
from narration.research.contracts import ResearchBudgetExhausted, WebDocument, WebSearchHit
from narration.research.web_research_worker import _parse_findings, _query_plan


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class _Session:
    def __init__(self, *payloads):
        self.payloads = iter(payloads)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response(next(self.payloads))


def test_tavily_adapter_search_extract_and_request_budget():
    url = "https://example.org/most"
    observed = []
    session = _Session(
        {"results": [{"title": "Most", "url": url, "content": "opis"},
                     {"title": "bad", "url": "javascript:x"}]},
        {"results": [{"url": url, "raw_content": "# Most\nOpis miejsca."}]},
    )
    client = TavilyResearchClient(
        api_key="test", max_requests=2, session=session,
        on_extract_raw_content=lambda *args: observed.append(args),
    )
    hits = client.search("Most Wrocław", max_results=5)
    assert len(hits) == 1
    assert hits[0].snippet == "opis"
    assert client.extract(hits[0], max_chars=8).content == "# Most\nO"
    assert observed == [(url, "# Most\nOpis miejsca.", 8)]
    assert client.request_count == 2
    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer test"
    with pytest.raises(ResearchBudgetExhausted):
        client.search("kolejne zapytanie", max_results=1)
    with pytest.raises(ValueError, match="returned by search"):
        client.extract(WebSearchHit("other", "https://other.org/", "", "x"), max_chars=20)


def test_tavily_observer_reports_empty_extraction_before_error():
    url = "https://example.org/galeria"
    observed = []
    client = TavilyResearchClient(
        api_key="test", max_requests=2,
        session=_Session(
            {"results": [{"title": "Galeria", "url": url}]},
            {"results": [{"url": url, "raw_content": ""}]},
        ),
        on_extract_raw_content=lambda *args: observed.append(args),
    )
    hit = client.search("galeria", max_results=1)[0]
    with pytest.raises(RuntimeError, match="returned no content"):
        client.extract(hit, max_chars=100)
    assert observed == [(url, "", 100)]


def test_markdown_cleanup_removes_link_only_navigation_but_preserves_prose():
    raw = (
        "* [Przejdź do menu głównego](#mainPageNav)\n"
        "* [Mapa serwisu](/mapa)\n"
        "[![Logo](https://example.org/logo.svg)](https://example.org/)\n"
        "# Historia dworca\n"
        "[Dworzec Nadodrze](https://example.org/dworzec) powstał w 1868 r. "
        "(w XIX wieku).\n"
        "* Budynek służył kolei i mieścił kasy biletowe.\n"
    )
    cleaned = clean_extracted_markdown(raw)
    assert "Przejdź do menu" not in cleaned
    assert "Mapa serwisu" not in cleaned
    assert "Logo" not in cleaned
    assert "# Historia dworca" in cleaned
    assert "Dworzec Nadodrze powstał w 1868 r. (w XIX wieku)." in cleaned
    assert "* Budynek służył kolei" in cleaned


def test_tavily_truncates_after_markdown_cleanup():
    url = "https://example.org/artykul"
    navigation = "".join("* [Menu](#menu)\n" for _ in range(30))
    client = TavilyResearchClient(
        api_key="test", max_requests=2,
        session=_Session(
            {"results": [{"title": "Artykuł", "url": url}]},
            {"results": [{"url": url, "raw_content": navigation + "Treść artykułu o dworcu."}]},
        ),
    )
    hit = client.search("dworzec", max_results=1)[0]
    assert client.extract(hit, max_chars=20).content == "Treść artykułu o dwo"


class _WebClient:
    def __init__(self, hits_by_query, documents):
        self.hits_by_query = hits_by_query
        self.documents = documents
        self.request_count = 0

    def search(self, query, *, max_results):
        self.request_count += 1
        return self.hits_by_query.get(query, [])[:max_results]

    def extract(self, hit, *, max_chars):
        self.request_count += 1
        document = self.documents[hit.url]
        return WebDocument(document.title, document.url, document.content[:max_chars])


class _Model:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.messages = []

    def generate(self, messages):
        self.messages.append(messages)
        return next(self.responses)


class _Locator:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def resolve(self, candidate, **kwargs):
        self.calls.append((candidate, kwargs))
        if not self.result:
            return None
        return PlaceCandidate.model_validate({
            **candidate.model_dump(),
            "lat": 51.1, "lon": 17.0,
            "coordinate_source": "nominatim:way:42",
            "external_ids": {"osm": "way:42"},
        })


def _location():
    return LocationContext(
        lat=51.1, lon=17.0, street="Ulica Testowa", neighbourhood="Nadodrze",
        city="Wrocław", region="Dolnośląskie", country="Polska",
    )


def _finding(content, **updates):
    item = {
        "scope": "PLACE", "anchor_name": "Most Testowy", "topic": "history",
        "content": content, "aliases": ["Kaiserbrücke"], "street": "Ulica Testowa",
    }
    item.update(updates)
    return json.dumps({"items": [item]}, ensure_ascii=False)


def test_worker_ranks_all_search_results_and_reads_two_documents_after_first_chunk():
    location = _location()
    area_query, street_query, city_query = _query_plan(location)
    assert area_query.startswith('"Nadodrze" "Wrocław"')
    assert street_query.startswith('ulica "Testowa" "Wrocław" "Nadodrze"')

    remote = WebSearchHit(
        "Dziedzictwo Bolesława Chrobrego", "https://example.org/krol",
        "Pierwszy król Polski i jego zabytki", area_query,
    )
    local = WebSearchHit(
        "Dworzec Nadodrze we Wrocławiu", "https://example.org/dworzec",
        "Historia dworca na Nadodrzu we Wrocławiu", street_query,
    )
    local_quote = "Dworzec Nadodrze powstał w XIX wieku i obsługiwał ruch kolejowy."
    remote_quote = "Katedra Wawelska była miejscem koronacji kolejnych królów Polski."
    client = _WebClient({
        area_query: [remote],
        street_query: [local],
        city_query: [local],
    }, {
        local.url: WebDocument(local.title, local.url, local_quote),
        remote.url: WebDocument(remote.title, remote.url, remote_quote),
    })
    model = _Model(json.dumps({"items": [
        {"scope": "PLACE", "anchor_name": "Dworzec Nadodrze", "topic": "history",
         "content": local_quote},
        {"scope": "PLACE", "anchor_name": "Katedra Wawelska", "city": "Kraków",
         "topic": "history", "content": remote_quote},
    ]}, ensure_ascii=False))
    store = InMemoryKnowledgeStore()

    report = TavilyResearchWorker(
        client, model, store, place_locator=_Locator(),
    ).run(location)

    assert report.queries == [area_query, street_query, city_query]
    assert [item.url for item in report.ranked_hits] == [local.url, remote.url]
    assert report.ranked_hits[0].score > report.ranked_hits[1].score
    assert report.extracted_urls == [local.url, remote.url]
    assert report.search_calls == 3
    assert report.extract_calls == 2
    assert report.llm_calls == len(model.messages) == 1
    assert report.api_request_count == 5
    assert len(report.chunk_ids) == len(store.places) == 2
    assert {place.city for place in store.places} == {"Wrocław", "Kraków"}
    assert all(len(chunk.source_ids) == 2 for chunk in store.chunks)
    assert all(set(chunk.source_urls) == {local.url, remote.url} for chunk in store.chunks)
    assert local_quote in model.messages[0][-1][1]
    assert remote_quote in model.messages[0][-1][1]


def test_worker_skips_empty_extraction_and_cites_only_successful_batch_urls():
    query = _query_plan(_location())[0]
    hits = [WebSearchHit(f"Nadodrze Wrocław {index}",
                         f"https://example.org/{index}", "historia Nadodrza", query)
            for index in range(3)]

    class Client(_WebClient):
        def extract(self, hit, *, max_chars):
            self.request_count += 1
            if hit.url == hits[0].url:
                raise RuntimeError("Tavily Extract returned no content")
            return self.documents[hit.url]

    texts = [
        "Budynek pierwszy powstał w dziewiętnastym wieku i służył lokalnej kolei.",
        "Budynek drugi został przebudowany po wojnie i mieścił warsztaty miejskie.",
    ]
    client = Client({query: hits}, {
        hits[1].url: WebDocument(hits[1].title, hits[1].url, texts[0]),
        hits[2].url: WebDocument(hits[2].title, hits[2].url, texts[1]),
    })
    model = _Model(_finding(
        "Most Testowy został przebudowany po wojnie i służył mieszkańcom dzielnicy.",
        aliases=["Stary Most"], street="",
    ))
    store = InMemoryKnowledgeStore()
    report = TavilyResearchWorker(
        client, model, store,
        WebResearchConfig(max_search_calls=1, max_extract_attempts=4),
        place_locator=_Locator(),
    ).run(_location())

    assert report.extract_calls == 3
    assert report.llm_calls == 1
    assert report.extracted_urls == [hits[1].url, hits[2].url]
    assert set(report.input_chars_by_url) == {hits[1].url, hits[2].url}
    assert len(store.chunks) == 1
    assert {source.url for source in store.sources} == set(report.extracted_urls)
    assert len(store.chunks[0].source_ids) == 2
    assert set(store.chunks[0].source_urls) == set(report.extracted_urls)
    assert set(store.places[0].aliases[0].source_ids) == set(store.chunks[0].source_ids)
    assert hits[0].url not in model.messages[0][-1][1]
    assert all(url not in model.messages[0][-1][1] for url in report.extracted_urls)
    assert all(text in model.messages[0][-1][1] for text in texts)
    assert any("returned no content" in error for error in report.errors)


def test_worker_stores_sourced_place_and_notifies_progressively():
    quote = (
        "Most Testowy, dawniej Kaiserbrücke, stoi przy Ulica Testowa "
        "we Wrocławiu i został opisany w kronice miejskiej."
    )
    hit = WebSearchHit("Historia mostu", "https://example.org/most", "Most we Wrocławiu", "q")
    client = _WebClient({
        _query_plan(_location())[0]: [hit],
    }, {hit.url: WebDocument(hit.title, hit.url, f"# Historia\n{quote}")})
    store = InMemoryKnowledgeStore()
    callback_snapshots = []
    worker = TavilyResearchWorker(client, _Model(_finding(quote)), store,
                                  place_locator=_Locator())

    report = worker.run(_location(), on_chunk=lambda chunk: callback_snapshots.append(
        (chunk.chunk_id, len(store.chunks))
    ))

    assert report.search_calls == 3
    assert report.extract_calls == 1
    assert report.llm_calls == 1
    assert report.new_chunk_count == 1
    assert report.api_request_count == 4
    assert report.first_chunk_latency_s is not None
    assert callback_snapshots == [(report.chunk_ids[0], 1)]
    assert len(store.sources) == len(store.places) == len(store.chunks) == 1
    assert store.sources[0].provider == "tavily"
    assert quote in store.sources[0].evidence_text
    assert store.places[0].aliases[0].name == "Kaiserbrücke"
    assert store.places[0].aliases[0].source_ids == [store.sources[0].source_id]
    assert (store.places[0].lat, store.places[0].lon) == (51.1, 17.0)
    assert store.chunks[0].scope == Scope.PLACE
    assert store.chunks[0].place_id == store.places[0].place_id
    assert store.chunks[0].source_ids == [store.sources[0].source_id]


def test_worker_accepts_paraphrase_without_quote_match_but_rejects_unrelated_area():
    document = WebDocument(
        "Wrocław", "https://example.org/city",
        "Wrocław leży nad Odrą i ma długą historię miejską.",
    )
    hit = WebSearchHit(document.title, document.url, "", "q")
    client = _WebClient({
        _query_plan(_location())[0]: [hit],
    }, {document.url: document})
    model = _Model(json.dumps({"items": [
        {"scope": "CITY", "anchor_name": "Wrocław", "topic": "history",
         "content": "Wrocław ma miejską historię związaną z Odrą i rozwijał się na jej brzegach."},
        {"scope": "CITY", "anchor_name": "Kraków", "topic": "geography",
         "content": "Kraków ma długą historię miejską i leży w południowej części Polski."},
    ]}, ensure_ascii=False))
    store = InMemoryKnowledgeStore()
    report = TavilyResearchWorker(client, model, store,
                                  place_locator=_Locator()).run(_location())
    assert len(report.chunk_ids) == len(store.sources) == len(store.chunks) == 1
    assert store.places == []
    assert store.chunks[0].content != document.content
    assert any("unrelated area" in error for error in report.errors)


def test_worker_applies_configured_chunk_length_without_literal_source_check():
    query = _query_plan(_location())[0]
    hit = WebSearchHit("Historia miasta", "https://example.org/miasto", "Wrocław", query)
    client = _WebClient({query: [hit]}, {
        hit.url: WebDocument(hit.title, hit.url, "Wrocław rozwijał się nad Odrą."),
    })
    model = _Model(json.dumps({"items": [
        {"scope": "CITY", "anchor_name": "Wrocław", "topic": "history",
         "content": "Za krótko."},
        {"scope": "CITY", "anchor_name": "Wrocław", "topic": "history",
         "content": "Miasto rozwijało się nad Odrą i przez stulecia zmieniało swój układ."},
    ]}, ensure_ascii=False))
    store = InMemoryKnowledgeStore()
    report = TavilyResearchWorker(
        client, model, store,
        WebResearchConfig(max_search_calls=1, max_extract_attempts=1,
                          max_successful_documents=1, min_chunk_chars=20),
        place_locator=_Locator(),
    ).run(_location())

    assert len(store.chunks) == 1
    assert store.chunks[0].content not in store.sources[0].evidence_text
    assert any("outside configured field limits" in error for error in report.errors)


def test_worker_respects_limits_and_reuses_located_place():
    quote = (
        "Most Testowy, dawniej Kaiserbrücke, stoi we Wrocławiu "
        "i został opisany w miejskim katalogu mostów."
    )
    hit = WebSearchHit("Most", "https://example.org/most", "", "q")
    client = _WebClient({
        _query_plan(_location())[0]: [hit],
    }, {hit.url: WebDocument(hit.title, hit.url, quote)})
    store = InMemoryKnowledgeStore()
    config = WebResearchConfig(max_search_calls=1, max_extract_attempts=1,
                               max_successful_documents=1)
    worker = TavilyResearchWorker(client, _Model(_finding(quote, street="")), store,
                                  config, place_locator=_Locator())
    worker.run(_location())
    second = TavilyResearchWorker(client, _Model(_finding(quote, street="")), store,
                                  config, place_locator=_Locator()).run(_location())
    assert second.search_calls == second.extract_calls == 1
    assert second.matched_place_count == 1
    assert len(store.places) == 1
    assert len(store.chunks) == 1


def test_worker_does_not_accept_missing_city_for_place_research():
    location = LocationContext(lat=51.1, lon=17.0, country="Polska")
    report = TavilyResearchWorker(_WebClient({}, {}), _Model(), InMemoryKnowledgeStore(),
                                  place_locator=_Locator()).run(location)
    assert report.search_calls == 0
    assert report.chunk_ids == []


def test_worker_keeps_source_but_not_place_when_coordinates_are_unresolved():
    quote = "Most Testowy, dawniej Kaiserbrücke, stoi we Wrocławiu przy Ulica Testowa."
    hit = WebSearchHit("Most", "https://example.org/most", "", "q")
    client = _WebClient({
        _query_plan(_location())[0]: [hit],
    }, {hit.url: WebDocument(hit.title, hit.url, quote)})
    store = InMemoryKnowledgeStore()
    report = TavilyResearchWorker(
        client, _Model(_finding(quote)), store,
        WebResearchConfig(max_search_calls=1, max_extract_attempts=1,
                          max_successful_documents=1),
        place_locator=_Locator(result=False),
    ).run(_location())
    assert report.unresolved_places == ["Most Testowy"]
    assert any("No supported coordinates for Most Testowy" in error for error in report.errors)
    assert len(store.sources) == 1
    assert store.places == store.chunks == []


def test_worker_geocodes_and_saves_place_with_its_chunk():
    quote = "Most Testowy stoi we Wrocławiu i jest częścią dawnego traktu handlowego."
    hit = WebSearchHit("Most", "https://example.org/most", "", "q")
    client = _WebClient({
        _query_plan(_location())[0]: [hit],
    }, {hit.url: WebDocument(hit.title, hit.url, quote)})

    class Search:
        def search_place(self, name, *, city, country="", limit=5):
            assert (name, city, country) == ("Most Testowy", "Wrocław", "Polska")
            return [GeocodedPlace(
                name="Most Testowy", lat=51.12, lon=17.04,
                city="Wrocław", country="Polska",
                coordinate_source="nominatim:way:42",
                external_ids={"osm": "way:42"},
            )]

    store = InMemoryKnowledgeStore()
    report = TavilyResearchWorker(
        client, _Model(_finding(quote)), store,
        WebResearchConfig(max_search_calls=1, max_extract_attempts=1,
                          max_successful_documents=1),
        place_locator=PlaceLocationResolver(Search()),
    ).run(_location())

    assert report.unresolved_places == []
    assert len(store.places) == len(store.chunks) == 1
    assert (store.places[0].lat, store.places[0].lon) == (51.12, 17.04)
    assert store.chunks[0].place_id == store.places[0].place_id


def test_model_can_identify_places_without_literal_anchor_or_nearby_city_in_quotes():
    first_quote = "Przeprawa powstała w latach trzydziestych i łączy dwa brzegi rzeki."
    second_quote = "Druga przeprawa została odbudowana po wojnie i służyła tramwajom."
    document = WebDocument(
        "Dzieje dwóch przepraw", "https://example.org/przeprawy",
        f"# Mosty\n{first_quote} {second_quote}",
    )
    hit = WebSearchHit(document.title, document.url, "", "q")
    client = _WebClient({
        _query_plan(_location())[0]: [hit],
    }, {document.url: document})
    model = _Model(json.dumps({"items": [
        {"scope": "CITY", "anchor_name": "Kraków", "topic": "geography",
         "content": first_quote},
        {"scope": "PLACE", "anchor_name": "Most Testowy", "topic": "history",
         "content": first_quote},
        {"scope": "PLACE", "anchor_name": "Most Odległy", "city": "Opole",
         "topic": "history", "content": second_quote},
    ]}, ensure_ascii=False))

    class Search:
        def __init__(self):
            self.cities = []

        def search_place(self, name, *, city, country="", limit=5):
            self.cities.append(city)
            return [GeocodedPlace(
                name=name, city=city, country=country,
                lat=51.1 if city == "Wrocław" else 50.67, lon=17.0,
                coordinate_source=f"test:{city}",
            )]

    search = Search()
    store = InMemoryKnowledgeStore()
    report = TavilyResearchWorker(
        client, model, store,
        WebResearchConfig(max_search_calls=1, max_extract_attempts=1,
                          max_successful_documents=1, max_total_chunks=2),
        place_locator=PlaceLocationResolver(search),
    ).run(_location())

    assert len(report.chunk_ids) == len(store.places) == 2
    assert search.cities == ["Wrocław", "Opole"]
    assert {chunk.city for chunk in store.chunks} == {"Wrocław", "Opole"}
    assert {chunk.anchor_name for chunk in store.chunks} == {"Most Testowy", "Most Odległy"}
    assert not any("unsupported place" in error for error in report.errors)


def test_store_keeps_distinct_evidence_from_repeated_reads_of_one_source():
    store = InMemoryKnowledgeStore()
    first = Source.from_url(
        provider="tavily", title="Page", url="https://example.org/page",
        evidence_text="Pierwszy udokumentowany fakt.",
    )
    second = Source.from_url(
        provider="tavily", title="Page", url="https://example.org/page",
        evidence_text="Drugi udokumentowany fakt.",
    )
    store.add_source(first)
    saved = store.add_source(second)
    assert first.evidence_text in saved.evidence_text
    assert second.evidence_text in saved.evidence_text


def test_model_json_may_be_wrapped_in_markdown_or_explanation():
    response = (
        "Analiza gotowa.\n```json\n"
        '{"items":[{"scope":"CITY","anchor_name":"Wrocław",'
        '"topic":"history","content":"Wrocław ma bogatą historię miejską."}]}'
        "\n```"
    )
    assert _parse_findings(response)[0].anchor_name == "Wrocław"
    with pytest.raises(ValueError, match="no valid findings JSON"):
        _parse_findings("Oto wyniki bez JSON")
