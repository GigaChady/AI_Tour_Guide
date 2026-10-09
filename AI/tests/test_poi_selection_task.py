from narration.poi_selection.poi_selection_task import PoiSelectionTask
from narration.schemas import PoiCandidate


def test_poi_selection_prefers_nearest_candidate_when_popularity_is_equal():
    task = PoiSelectionTask()
    candidates = [
        PoiCandidate(name="Far Museum", category="museum", lat=50.10, lon=19.90),
        PoiCandidate(name="Near Artwork", category="artwork", lat=50.001, lon=19.001),
    ]

    selected = task.run(
        candidates=candidates,
        user_latitude=50.0,
        user_longitude=19.0,
    )

    assert selected is not None
    assert selected.poi.name == "Near Artwork"


def test_poi_selection_uses_category_rank_when_distance_matches():
    task = PoiSelectionTask()
    candidates = [
        PoiCandidate(name="Artwork", category="artwork", lat=50.0, lon=19.0),
        PoiCandidate(name="Museum", category="museum", lat=50.0, lon=19.0),
    ]

    selected = task.run(
        candidates=candidates,
        user_latitude=50.0,
        user_longitude=19.0,
    )

    assert selected is not None
    assert selected.poi.name == "Museum"


def test_poi_selection_prefers_wikipedia_candidate_over_slightly_nearer_poi():
    task = PoiSelectionTask()
    candidates = [
        PoiCandidate(
            name="Nearby Artwork",
            category="artwork",
            lat=50.001,
            lon=19.001,
        ),
        PoiCandidate(
            name="Known Monument",
            category="monument",
            lat=50.01,
            lon=19.01,
            wikipedia="pl:Known_Monument",
        ),
    ]

    selected = task.run(
        candidates=candidates,
        user_latitude=50.0,
        user_longitude=19.0,
    )

    assert selected is not None
    assert selected.poi.name == "Known Monument"


def test_poi_selection_prefers_wikidata_candidate_over_plain_candidate():
    task = PoiSelectionTask()
    candidates = [
        PoiCandidate(
            name="Plain Memorial",
            category="memorial",
            lat=50.001,
            lon=19.001,
        ),
        PoiCandidate(
            name="Known Memorial",
            category="memorial",
            lat=50.004,
            lon=19.004,
            wikidata="Q123",
        ),
    ]

    selected = task.run(
        candidates=candidates,
        user_latitude=50.0,
        user_longitude=19.0,
    )

    assert selected is not None
    assert selected.poi.name == "Known Memorial"
