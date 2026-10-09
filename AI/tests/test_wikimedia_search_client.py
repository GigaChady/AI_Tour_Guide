from integrations.knowledge.wikimedia.wikimedia_search_client import WikimediaSearchClient
from narration.schemas import LocationAddress, PoiCandidate, SelectedPoi


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, empty_extract=False):
        self.requests = []
        self.empty_extract = empty_extract

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        params = kwargs.get("params", {})
        if params.get("prop") == "extracts":
            return FakeResponse(
                {
                    "query": {
                        "pages": {
                            "123": {
                                "title": "Gertraudendenkmal",
                                "extract": "" if self.empty_extract else (
                                    "Gertraudendenkmal is a memorial in Berlin. "
                                    "It has a longer encyclopedic description that can "
                                    "give the narrator more context than a short summary."
                                ),
                            }
                        }
                    }
                }
            )
        if "api/rest_v1/page/summary" in url:
            return FakeResponse(
                {
                    "title": "Gertraudendenkmal",
                    "extract": "Gertraudendenkmal is a memorial in Berlin.",
                }
            )
        return FakeResponse({"query": {"search": [{"title": "Gertraudendenkmal"}]}})


def test_wikimedia_client_uses_wikipedia_tag_before_search():
    session = FakeSession()
    client = WikimediaSearchClient(session=session)
    selected = SelectedPoi(
        poi=PoiCandidate(
            name="Gertraudendenkmal",
            category="memorial",
            lat=52.513,
            lon=13.401,
            wikipedia="de:Gertraudendenkmal",
        ),
        distance_km=0.12,
        category_rank=2,
    )

    result = client.search_poi(selected, LocationAddress())

    assert "Wikipedia (de) title: Gertraudendenkmal" in result
    assert "Extract:" in result
    assert "longer encyclopedic description" in result
    assert len(session.requests) == 1
    assert "de.wikipedia.org/w/api.php" in session.requests[0][0]
    assert session.requests[0][1]["params"]["prop"] == "extracts"


def test_wikimedia_client_searches_page_extract_when_no_tags_exist():
    session = FakeSession()
    client = WikimediaSearchClient(session=session, languages=("pl",))
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

    result = client.search_poi(selected, address)

    assert "longer encyclopedic description" in result
    assert len(session.requests) == 2
    assert "pl.wikipedia.org/w/api.php" in session.requests[0][0]
    assert session.requests[0][1]["params"]["srsearch"] == "Gertraudendenkmal Berlin, Germany"
    assert session.requests[1][1]["params"]["prop"] == "extracts"


def test_wikimedia_client_falls_back_to_summary_when_extract_is_empty():
    session = FakeSession(empty_extract=True)
    client = WikimediaSearchClient(session=session, languages=("pl",))
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

    result = client.search_poi(selected, LocationAddress())

    assert "Summary: Gertraudendenkmal is a memorial in Berlin." in result
    assert len(session.requests) == 3
    assert "api/rest_v1/page/summary" in session.requests[2][0]
