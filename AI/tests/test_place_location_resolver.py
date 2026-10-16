from types import SimpleNamespace

from integrations.geocoding.nominatim.nominatim_client import NominatimClient
from integrations.knowledge.wikimedia.wikimedia_article_provider import WikimediaArticleProvider
from narration.knowledge import (
    GeocodedPlace,
    InMemoryKnowledgeStore,
    LocationContext,
    PlaceAlias,
    PlaceCandidate,
    PlaceLocationResolver,
    Source,
)


def _candidate(name="Mosty Bolesława Chrobrego", street=""):
    return PlaceCandidate(name=name, city="Wrocław", street=street, source_ids=["source:1"])


def _location():
    return LocationContext(lat=51.1216, lon=17.0352, city="Wrocław", country="Polska")


def _result(name, lat, lon, *, district="", city="Wrocław", country="Polska", street=""):
    return GeocodedPlace(
        name=name, lat=lat, lon=lon, city=city, country=country,
        district=district, street=street,
        coordinate_source=f"nominatim:way:{round(lat * 100000)}",
        external_ids={"osm": f"way:{round(lat * 100000)}"},
    )


class _Search:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search_place(self, name, *, city, country="", limit=5):
        self.calls.append((name, city, country, limit))
        return self.results


class _Wiki:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def find_place_coordinates(self, name, *, disambiguator=""):
        self.calls.append((name, disambiguator))
        return self.result


def test_wikipedia_coordinates_are_used_for_wikipedia_place():
    wiki = _Wiki(GeocodedPlace(
        name="Mosty Bolesława Chrobrego", lat=51.15, lon=17.08,
        city="Wrocław", coordinate_source="wikipedia:pl:123",
        external_ids={"wikidata": "Q123"},
    ))
    search = _Search([])
    located = PlaceLocationResolver(search, wiki).resolve(
        _candidate(), source_url="https://pl.wikipedia.org/wiki/Mosty_Boleslawa_Chrobrego",
        source_text="Mosty Bolesława Chrobrego we Wrocławiu.",
        research_location=_location(),
    )
    assert located is not None
    assert (located.lat, located.lon) == (51.15, 17.08)
    assert located.coordinate_source == "wikipedia:pl:123"
    assert located.external_ids["wikidata"] == "Q123"
    assert len(located.locations) == 1
    assert search.calls == []


def test_wikipedia_without_coordinates_falls_back_to_nominatim():
    wiki = _Wiki(None)
    search = _Search([_result("Mosty Bolesława Chrobrego", 51.15, 17.08)])
    located = PlaceLocationResolver(search, wiki).resolve(
        _candidate(), source_url="https://pl.wikipedia.org/wiki/Mosty_Boleslawa_Chrobrego",
        source_text="Mosty Bolesława Chrobrego we Wrocławiu.",
        research_location=_location(),
    )
    assert located is not None
    assert located.coordinate_source.startswith("nominatim:")
    assert wiki.calls == [("Mosty Bolesława Chrobrego", "Wrocław")]
    assert len(search.calls) == 1


def test_nearest_name_match_is_representative_and_result_is_cached():
    near = _result("Mosty Bolesława Chrobrego", 51.1217, 17.0353, district="Nadodrze")
    far = _result("Mosty Bolesława Chrobrego", 51.15, 17.08, district="Swojczyce")
    search = _Search([near, far])
    locator = PlaceLocationResolver(search)
    arguments = dict(
        source_url="https://example.org/bridge",
        source_text="Mosty Bolesława Chrobrego łączą Swojczyce z Sępolnem.",
        research_location=_location(),
    )
    assert locator.resolve(_candidate(), **arguments).lat == near.lat
    assert locator.resolve(_candidate(), **arguments).lat == near.lat
    assert len(search.calls) == 1


def test_distance_breaks_tie_after_name_city_and_country_checks():
    wrong_city = _result("Mosty Bolesława Chrobrego", 51.1216, 17.0352, city="Kraków")
    wrong_street = _result("Mosty Bolesława Chrobrego", 51.1217, 17.0353,
                           street="Inna")
    farther = _result("Mosty Bolesława Chrobrego", 51.16, 17.09,
                      street="Chrobrego")
    nearer = _result("Mosty Bolesława Chrobrego", 51.15, 17.08,
                     street="Chrobrego")
    located = PlaceLocationResolver(_Search([
        wrong_city, wrong_street, farther, nearer,
    ])).resolve(
        _candidate(street="ul. Chrobrego"), source_url="https://example.org/bridge",
        source_text="Mosty Bolesława Chrobrego przy ul. Chrobrego.",
        research_location=_location(),
    )
    assert located is not None
    assert located.lat == wrong_street.lat
    assert {point.coordinate_source for point in located.locations} == {
        wrong_street.coordinate_source, farther.coordinate_source,
        nearer.coordinate_source,
    }


def test_mismatched_street_does_not_reject_station_coordinates():
    station = _result("Wrocław Nadodrze", 51.12, 17.03, street="Ołbińska")
    candidate = PlaceCandidate(
        name="Wrocław Nadodrze", city="Wrocław", street="pl. Staszica",
        source_ids=["source:1"],
    )
    located = PlaceLocationResolver(_Search([station])).resolve(
        candidate, source_url="https://example.org/station", source_text="Dworzec.",
        research_location=_location(),
    )
    assert located is not None
    assert (located.lat, located.lon) == (station.lat, station.lon)
    assert located.street == "pl. Staszica"
    assert located.locations[0].street == "Ołbińska"


def test_country_still_filters_matching_name_and_city():
    wrong_country = _result("Wrocław Nadodrze", 51.1216, 17.0352, country="Niemcy")
    valid = _result("Wrocław Nadodrze", 51.12, 17.03)
    located = PlaceLocationResolver(_Search([wrong_country, valid])).resolve(
        PlaceCandidate(name="Wrocław Nadodrze", city="Wrocław", source_ids=["source:1"]),
        source_url="https://example.org/station", source_text="Dworzec.",
        research_location=_location(),
    )
    assert located is not None
    assert located.coordinate_source == valid.coordinate_source
    assert [point.coordinate_source for point in located.locations] == [valid.coordinate_source]


def test_unrelated_search_results_do_not_create_a_location():
    locator = PlaceLocationResolver(_Search([
        _result("Ulica Bolesława Chrobrego", 51.12, 17.03),
    ]))
    assert locator.resolve(
        _candidate(), source_url="https://example.org/bridge",
        source_text="Mosty Bolesława Chrobrego we Wrocławiu.",
        research_location=_location(),
    ) is None


def test_unresolved_location_reports_which_filters_rejected_nominatim_results():
    search = _Search([
        _result("Ulica Bolesława Chrobrego", 51.12, 17.03),
        _result("Mosty Bolesława Chrobrego", 50.06, 19.94, city="Kraków"),
    ])
    candidate = PlaceCandidate(
        name="Mosty Bolesława Chrobrego", city="Wrocław",
        aliases=[PlaceAlias(name="Mosty Chrobrego", source_id="source:1")],
        source_ids=["source:1"],
    )
    diagnostics = []

    assert PlaceLocationResolver(search).resolve(
        candidate, source_url="https://example.org/bridge",
        source_text="Mosty Chrobrego we Wrocławiu.",
        research_location=_location(), diagnostics=diagnostics,
    ) is None

    assert len(search.calls) == 1
    assert "Nominatim returned 2 results for primary name" in diagnostics
    assert "Rejected Nominatim results: name=1, city=1, country=0" in diagnostics
    assert "Alias lookup skipped because primary search returned results" in diagnostics


def test_bridge_keeps_every_matching_segment_and_relation_in_one_place():
    first_way = _result("Mosty Bolesława Chrobrego", 51.1141, 17.1084)
    second_way = _result("Mosty Bolesława Chrobrego", 51.1136, 17.1076)
    relation = GeocodedPlace(
        name="Mosty Chrobrego", lat=51.11412, lon=17.10838,
        city="Wrocław", country="Polska",
        coordinate_source="nominatim:relation:19510223",
        external_ids={"osm": "relation:19510223"},
    )
    locator = PlaceLocationResolver(_Search([first_way, second_way, relation]))
    store = InMemoryKnowledgeStore()
    source = store.add_source(Source.from_url(
        provider="tavily", title="Mosty Chrobrego", url="https://example.org/bridge",
    ))
    representatives = set()
    for lat, lon in ((51.1216, 17.0352), (51.1100, 17.1600)):
        located = locator.resolve(
            PlaceCandidate(name="Mosty Bolesława Chrobrego", city="Wrocław",
                           source_ids=[source.source_id]),
            source_url=source.url,
            source_text="Mosty Bolesława Chrobrego we Wrocławiu.",
            research_location=LocationContext(lat=lat, lon=lon, city="Wrocław", country="Polska"),
        )
        assert located is not None
        representatives.add(located.coordinate_source)
        assert {point.coordinate_source for point in located.locations} == {
            first_way.coordinate_source, second_way.coordinate_source,
            relation.coordinate_source,
        }
        store.resolve_place(located)
    assert len(representatives) == 2
    assert len(store.places) == 1
    assert {point.coordinate_source for point in store.places[0].locations} == {
        first_way.coordinate_source, second_way.coordinate_source,
        relation.coordinate_source,
    }


def test_nominatim_adapter_returns_coordinates_and_source_id():
    raw = {
        "osm_type": "way", "osm_id": 42,
        "name": "Mosty Bolesława Chrobrego",
        "display_name": "Mosty Bolesława Chrobrego, Wrocław, Polska",
        "namedetails": {"name": "Mosty Bolesława Chrobrego", "alt_name": "Mosty Swojczyckie"},
        "address": {"city": "Wrocław", "country": "Polska", "suburb": "Swojczyce"},
    }
    class Geolocator:
        def geocode(self, query, **kwargs):
            self.query, self.kwargs = query, kwargs
            return [SimpleNamespace(raw=raw, latitude=51.15, longitude=17.08,
                                    address=raw["display_name"])]
    geolocator = Geolocator()
    client = NominatimClient(geolocator=geolocator, min_interval_seconds=0)
    results = client.search_place("Mosty Bolesława Chrobrego", city="Wrocław", country="Polska")
    assert geolocator.query == "Mosty Bolesława Chrobrego, Wrocław, Polska"
    assert geolocator.kwargs["exactly_one"] is False
    assert results[0].coordinate_source == "nominatim:way:42"
    assert results[0].external_ids == {"osm": "way:42"}
    assert "Mosty Swojczyckie" in results[0].aliases


def test_wikimedia_provider_reads_primary_article_coordinates():
    page = {"query": {"pages": [{
        "pageid": 123, "title": "Mosty Bolesława Chrobrego", "extract": "Mosty we Wrocławiu.",
        "pageprops": {"wikibase_item": "Q123"},
        "coordinates": [{"lat": 51.15, "lon": 17.08, "globe": "earth"}],
    }]}}
    class Session:
        def get(self, url, **kwargs):
            self.params = kwargs["params"]
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: page)
    session = Session()
    provider = WikimediaArticleProvider(
        user_agent="TourGuideTest/1.0 (test@example.org)", languages=("pl",), session=session,
    )
    result = provider.find_place_coordinates("Mosty Bolesława Chrobrego", disambiguator="Wrocław")
    assert result is not None
    assert (result.lat, result.lon) == (51.15, 17.08)
    assert result.external_ids["wikidata"] == "Q123"
    assert "coordinates" in session.params["prop"]


def test_wikimedia_coordinates_need_city_context():
    page = {"query": {"pages": [{
        "pageid": 123, "title": "Most Testowy", "extract": "Most znajduje się w Krakowie.",
        "coordinates": [{"lat": 50.06, "lon": 19.94, "globe": "earth"}],
    }]}}
    class Session:
        def get(self, url, **kwargs):
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: page)
    provider = WikimediaArticleProvider(
        user_agent="TourGuideTest/1.0 (test@example.org)", languages=("pl",), session=Session(),
    )
    assert provider.find_place_coordinates("Most Testowy", disambiguator="Wrocław") is None
