from narration.schemas import (
    NarrationResult,
    PoiCandidate,
    SelectedPoi,
    TourPipelineResult,
)
from workers.redis_narration.narration_event_handler import NarrationEventHandler


class FakePhotoProcessor:
    def __init__(self):
        self.calls = []

    def generate(self, category, count):
        self.calls.append((category, count))
        return f"https://example.test/{category}-{count}.jpg"


class FakePipeline:
    def __init__(self, result):
        self.result = result
        self.request = None

    def run(self, request):
        self.request = request
        return self.result


def test_handler_maps_event_runs_pipeline_and_builds_messages():
    poi = PoiCandidate(
        name="Museum",
        category="museum",
        lat=50.0,
        lon=19.0,
    )
    pipeline = FakePipeline(
        TourPipelineResult(
            selected_poi=SelectedPoi(
                poi=poi,
                distance_km=0.0,
                category_rank=1,
            ),
            narration=NarrationResult(
                location="Museum",
                narration="Narration",
            ),
        )
    )
    photos = FakePhotoProcessor()
    handler = NarrationEventHandler(
        pipeline=pipeline,
        photo_processor=photos,
        mock_enabled=False,
    )

    result = handler.handle(
        entry_id="1-0",
        payload={
            "session_id": "session-1",
            "lat": "50.0",
            "lng": "19.0",
            "include_photos": "2",
        },
        preferences={"interests": ["history"]},
    )

    assert pipeline.request.session_id == "session-1"
    assert pipeline.request.settings.user_preferences == "history"
    assert result.session_id == "session-1"
    assert result.narration.text == "Narration"
    assert result.pois.data[0].name == "Museum"
    assert result.pois.data[0].photos == [
        "https://example.test/museum-0.jpg",
        "https://example.test/museum-1.jpg",
    ]
    assert photos.calls == [("museum", 0), ("museum", 1)]


def test_handler_returns_planning_pois_without_narration():
    poi = PoiCandidate(
        name="Museum",
        category="museum",
        lat=50.0,
        lon=19.0,
    )
    pipeline = FakePipeline(
        TourPipelineResult(
            selected_pois=[
                SelectedPoi(
                    poi=poi,
                    distance_km=0.0,
                    category_rank=1,
                )
            ]
        )
    )
    handler = NarrationEventHandler(
        pipeline=pipeline,
        photo_processor=None,
        mock_enabled=False,
    )

    result = handler.handle(
        entry_id="1-0",
        payload={
            "session_id": "session-1",
            "lat": 50.0,
            "lng": 19.0,
            "is_narration": False,
        },
        preferences={},
    )

    assert result.narration is None
    assert result.pois.data[0].name == "Museum"
