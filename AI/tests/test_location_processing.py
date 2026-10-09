from integrations.poi.overpass.overpass_models import OverpassResponse
from integrations.poi.overpass.overpass_poi_parser import OverpassPoiParser
from narration.location_discovery.location_discovery_task import LocationDiscoveryTask
from narration.schemas import (
    LocationAddress,
    NarrationDetailLevel,
    NarrationLanguage,
    NarrationSettings,
)


class FakeGeocodingClient:
    def __init__(self):
        self.calls = []

    def reverse_geocode(self, lat, lon, language_tag, zoom_level):
        self.calls.append((lat, lon, language_tag, zoom_level))
        return LocationAddress(
            raw={"address": {"city": "Krakow", "suburb": "Old Town"}}
        )


class FakeOverpassClient:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def get_nearby_poi_data(self, lat, lon, radius):
        self.calls.append((lat, lon, radius))
        return OverpassResponse.model_validate(self.data)


def _settings():
    return NarrationSettings(
        latitude=50.0614,
        longitude=19.9372,
        detail_level=NarrationDetailLevel.DETAILED,
        search_radius=100,
        language=NarrationLanguage(language_name="Polish", language_tag="pl"),
        user_preferences="history",
    )


def test_overpass_poi_parser_filters_and_deduplicates_pois():
    parser = OverpassPoiParser()
    data = {
        "elements": [
            {
                "lat": 50.0,
                "lon": 19.0,
                "tags": {
                    "name": "Museum",
                    "tourism": "museum",
                    "website": "https://example.test",
                },
            },
            {
                "lat": 50.0,
                "lon": 19.0,
                "tags": {"name": "museum", "tourism": "museum"},
            },
            {
                "lat": 50.1,
                "lon": 19.1,
                "tags": {"name": "Hotel", "tourism": "hotel"},
            },
            {
                "center": {"lat": 50.2, "lon": 19.2},
                "tags": {"name": "Old Fort", "historic": "fort"},
            },
            {
                "tags": {"name": "No Coordinates", "tourism": "attraction"},
            },
        ]
    }

    pois = parser.parse(OverpassResponse.model_validate(data))

    assert len(pois) == 2
    assert pois[0].name == "museum"
    assert pois[0].category == "museum"
    assert pois[1].name == "Old Fort"
    assert pois[1].lat == 50.2


def test_location_processor_uses_clients_and_parser():
    overpass_data = {
        "elements": [
            {
                "lat": 50.0,
                "lon": 19.0,
                "tags": {"name": "Museum", "tourism": "museum"},
            }
        ]
    }
    geocoding_client = FakeGeocodingClient()
    overpass_client = FakeOverpassClient(overpass_data)

    processor = LocationDiscoveryTask(
        geocoding_client=geocoding_client,
        poi_data_client=overpass_client,
        poi_parser=OverpassPoiParser(),
    )

    details = processor.get_location_details(_settings())

    assert details.address.city == "Krakow"
    assert details.candidates[0].name == "Museum"
    assert geocoding_client.calls == [
        (50.0614, 19.9372, "pl", NarrationDetailLevel.DETAILED)
    ]
    assert overpass_client.calls == [(50.0614, 19.9372, 100)]
