import struct
from types import SimpleNamespace

from integrations.geocoding.gus_address_client import GusAddressClient
from integrations.geocoding.overture_places_client import OverturePlacesClient
from narration.knowledge.address_evidence import SupportedAddress, supported_address
from narration.knowledge.models import GeocodedPlace, LocationContext, PlaceCandidate
from narration.knowledge.models import Source
from narration.knowledge.store import InMemoryKnowledgeStore
from narration.knowledge.place_location_resolver import PlaceLocationResolver


LOCATION = LocationContext(lat=51.1216, lon=17.0352, city="Wrocław", country="Polska")
SOURCE = "Kolorowe podwórka przy ul. Roosevelta 14 we Wrocławiu powstały z udziałem mieszkańców."


def _candidate(address="ul. Roosevelta 14, Wrocław"):
    return PlaceCandidate(name="Kolorowe podwórka", city="Wrocław", address=address,
                          source_ids=["source:1"])


def _point(source="gus_address:1", *, city="Wrocław", street="Roosevelta", number="14"):
    return GeocodedPlace(
        name="Roosevelta 14" if source.startswith("gus") else "Kolorowe podwórka",
        lat=51.121, lon=17.035, city=city, country="Polska", street=street,
        house_number=number, location_type="address" if source.startswith("gus") else "place",
        coordinate_source=source,
        external_ids={"gus_address": source.partition(":")[2]}
        if source.startswith("gus") else {},
    )


class Search:
    def __init__(self, points=()):
        self.points = list(points)
        self.calls = 0

    def search_place(self, *args, **kwargs):
        self.calls += 1
        return self.points


class AddressSearch:
    def __init__(self, points=()):
        self.points = list(points)
        self.calls = []

    def search_address(self, address, *, country=""):
        self.calls.append((address, country))
        return self.points


class OvertureSearch:
    def __init__(self, points=()):
        self.points = list(points)
        self.calls = 0

    def search_place(self, *args, **kwargs):
        self.calls += 1
        return self.points


def test_address_must_be_numbered_and_supported_by_source():
    accepted, _ = supported_address(
        "ul. Roosevelta 14, Wrocław", city="Wrocław", source_text=SOURCE, max_chars=200
    )
    assert accepted == SupportedAddress("Roosevelta", "14", "Wrocław")
    for address in ("pl. Staszica", "ul. Roosevelta 14-16, Wrocław",
                    "ul. Roosevelta 14, Kraków", "ul. Nieistniejąca 14, Wrocław"):
        rejected, _ = supported_address(
            address, city="Wrocław", source_text=SOURCE, max_chars=200
        )
        assert rejected is None


def test_exact_address_is_used_before_place_catalogues():
    address = AddressSearch([_point()])
    overture = OvertureSearch([_point("overture:1")])
    nominatim = Search([_point("nominatim:way:1")])
    locator = PlaceLocationResolver(nominatim, address_client=address, overture_client=overture)
    notes = []
    result = locator.resolve(_candidate(), source_url="", source_text=SOURCE,
                             research_location=LOCATION, diagnostics=notes)
    assert result.coordinate_source == "gus_address:1"
    assert result.locations[0].location_type == "address"
    assert len(address.calls) == 1
    assert overture.calls == nominatim.calls == 0
    assert "Address geocoder returned 1 exact points" in notes


def test_shared_address_does_not_merge_distinct_places():
    address = AddressSearch([_point()])
    locator = PlaceLocationResolver(Search(), address_client=address)
    store = InMemoryKnowledgeStore()
    source = store.add_source(Source.from_url(
        provider="tavily", title="Dwa obiekty", url="https://example.org/obiekty",
    ))
    for name in ("Galeria Testowa", "Kawiarnia Testowa"):
        candidate = PlaceCandidate(
            name=name, city="Wrocław", address="ul. Roosevelta 14, Wrocław",
            source_ids=[source.source_id],
        )
        located = locator.resolve(candidate, source_url=source.url, source_text=SOURCE,
                                  research_location=LOCATION)
        assert located.external_ids == {}
        assert located.locations[0].external_ids == {"gus_address": "1"}
        store.resolve_place(located)
    assert len(store.places) == 2


def test_unsupported_address_falls_back_to_overture_without_geocoding_it():
    address = AddressSearch([_point()])
    overture = OvertureSearch([_point("overture:1")])
    nominatim = Search()
    locator = PlaceLocationResolver(nominatim, address_client=address, overture_client=overture)
    notes = []
    result = locator.resolve(_candidate("ul. Nieistniejąca 14, Wrocław"),
                             source_url="", source_text=SOURCE,
                             research_location=LOCATION, diagnostics=notes)
    assert result.coordinate_source == "overture:1"
    assert result.address == ""
    assert address.calls == []
    assert nominatim.calls == 0
    assert any("Address ignored" in note for note in notes)


def test_ambiguous_address_and_empty_overture_continue_to_nominatim():
    address = AddressSearch([_point("gus_address:1"), _point("gus_address:2")])
    overture = OvertureSearch()
    nominatim = Search([_point("nominatim:way:1")])
    locator = PlaceLocationResolver(nominatim, address_client=address, overture_client=overture)
    notes = []
    result = locator.resolve(_candidate(), source_url="", source_text=SOURCE,
                             research_location=LOCATION, diagnostics=notes)
    assert result.coordinate_source == "nominatim:way:1"
    assert overture.calls == nominatim.calls == 1
    assert any("ambiguous" in note for note in notes)


def test_gus_adapter_requires_matching_number_street_city_and_point():
    rows = [{"single": {
        "id": 7, "miejsc_nazwa": "Wrocław", "ul_pelna": "Roosevelta", "pkt_numer": "14",
        "geometry": {"type": "Point", "coordinates": [17.035, 51.121]},
    }}, {"single": {
        "id": 8, "miejsc_nazwa": "Wrocław", "ul_pelna": "Roosevelta", "pkt_numer": "16",
        "geometry": {"type": "Point", "coordinates": [17.036, 51.122]},
    }}]
    class Session:
        def post(self, url, **kwargs):
            self.payload = kwargs["json"]
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: rows)
    session = Session()
    client = GusAddressClient(session=session)
    found = client.search_address(SupportedAddress("Roosevelta", "14", "Wrocław"),
                                  country="Polska")
    assert len(found) == 1
    assert found[0].coordinate_source == "gus_address:7"
    assert found[0].lat == 51.121 and found[0].lon == 17.035
    assert session.payload["reqs"][0]["pkt_numer"] == "14"


def test_overture_adapter_reads_point_and_caches_area():
    calls = []
    row = {
        "id": "gers-1", "names": {"primary": "Kolorowe podwórka", "common": {}},
        "addresses": [{"locality": "Wrocław"}],
        "geometry": struct.pack("<BIdd", 1, 1, 17.035, 51.121),
    }
    def reader(kind, *, bbox):
        calls.append((kind, bbox))
        return SimpleNamespace(read_all=lambda: SimpleNamespace(to_pylist=lambda: [row]))
    client = OverturePlacesClient(record_reader=reader)
    first = client.search_place(_candidate(""), research_location=LOCATION)
    second = client.search_place(_candidate(""), research_location=LOCATION)
    assert first[0].coordinate_source == "overture:gers-1"
    assert second == first
    assert len(calls) == 1
    assert client.search_place(PlaceCandidate(name="Kolorowe podwórka", city="Kraków",
                                              source_ids=["source:1"]),
                               research_location=LOCATION) == []
