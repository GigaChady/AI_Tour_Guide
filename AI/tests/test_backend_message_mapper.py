from narration.schemas import NarrationDetailLevel, NarrationResult, PoiCandidate
from workers.redis_narration.backend_message_mapper import BackendMessageMapper
from workers.redis_narration.messages import LocationEvent, PreferencesEvent


class FakeDefaults:
    default_detail_level = NarrationDetailLevel.DETAILED
    default_search_radius = 2500
    default_language = "pl"
    default_language_name = "Polish"
    ollama_base_url = "http://ollama:11434"


def test_mapper_builds_narration_settings_from_backend_events():
    mapper = BackendMessageMapper()
    location = LocationEvent(
        session_id="session-1",
        lat=50.0,
        lng=19.0,
        include_photos=0,
        is_narration=False,
    )
    prefs = PreferencesEvent(interests=["history", "architecture"])

    settings = mapper.build_narration_settings(
        location=location,
        prefs=prefs,
        defaults=FakeDefaults(),
    )

    assert settings.latitude == 50.0
    assert settings.longitude == 19.0
    assert settings.search_radius == 2500
    assert settings.language.language_tag == "pl"
    assert settings.user_preferences == "history, architecture"
    assert settings.include_narration is False
    assert settings.photo_count == 1


def test_mapper_builds_backend_messages_from_pipeline_models():
    mapper = BackendMessageMapper()
    poi = PoiCandidate(
        name="Town Hall Tower",
        category="monument",
        lat=50.0616,
        lon=19.9373,
    )
    narration = NarrationResult(
        location="Town Hall Tower",
        narration="A short story about the tower.",
    )

    pois_message = mapper.build_pois_message(
        poi=poi,
        photos=["https://example.test/photo.jpg"],
    )
    narration_message = mapper.build_narration_message(narration)

    assert pois_message.type == "pois"
    assert len(pois_message.data) == 1
    assert pois_message.data[0].name == "Town Hall Tower"
    assert pois_message.data[0].lng == 19.9373
    assert pois_message.data[0].photos == ["https://example.test/photo.jpg"]
    assert narration_message.type == "narration"
    assert narration_message.text == "A short story about the tower."
