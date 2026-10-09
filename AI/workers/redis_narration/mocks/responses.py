from pathlib import Path

from workers.redis_narration.messages import NarrationMessage, Poi, PreferencesEvent


def mock_pois(session_id: str, lat: float, lng: float) -> list[Poi]:
    return [
        Poi(
            name="Mock Museum",
            lat=lat + 0.0005,
            lng=lng + 0.0005,
            desc="Mock point of interest generated from Redis Stream input.",
            photos=[
                mock_image_url(
                    "Mock Museum",
                    Path(__file__).parents[3] / "photos" / "assets" / "mock_images" / "museum_mock.jpg",
                )
            ],
        )
    ]


def mock_narration(
    session_id: str,
    preferences: PreferencesEvent,
    lat: float,
    lng: float,
    pois: list[Poi],
    narration=None,
) -> NarrationMessage:
    text = (
        f"Mock narration for session {session_id}. "
        f"User is near {lat:.5f}, {lng:.5f}. "
        f"Suggested stops: {', '.join(p.name for p in pois)}."
        f"User preferences: {preferences}."
        f"Real narration: {narration}"
    )
    return NarrationMessage(text=text)


def mock_image_url(poi_name: str, filepath: str | Path) -> str:
    from integrations.storage.minio.minio_image_storage import MinioImageStorage

    image_bytes = Path(filepath).read_bytes()
    storage = MinioImageStorage()

    storage_name = poi_name.replace(" ", "_").lower() + ".jpg"

    result = storage.upload_bytes(storage_name, image_bytes)  # WARNING: switch to poi_id in production to avoid duplicates
    return result["image_url"]
