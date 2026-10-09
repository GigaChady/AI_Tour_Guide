from __future__ import annotations

from typing import Any

from narration.config import NarrationDefaultsConfig
from narration.schemas import (
    NarrationDetailLevel,
    NarrationLanguage,
    NarrationResult,
    NarrationSettings,
    PoiCandidate,
)
from workers.redis_narration.messages import (
    LocationEvent,
    NarrationMessage,
    Poi,
    PoisMessage,
    PreferencesEvent,
)


class BackendMessageMapper:
    def build_narration_settings(
        self,
        location: LocationEvent,
        prefs: PreferencesEvent,
        defaults: Any | None = None,
    ) -> NarrationSettings:
        if not isinstance(location, LocationEvent) or not isinstance(prefs, PreferencesEvent):
            raise ValueError("Expected LocationEvent and PreferencesEvent instances")

        defaults = defaults or NarrationDefaultsConfig()
        detail_level = getattr(
            prefs,
            "detail_level",
            defaults.default_detail_level.value,
        )
        language_tag = getattr(prefs, "language", defaults.default_language)
        language_name = getattr(
            prefs,
            "language_name",
            defaults.default_language_name,
        )
        user_preferences = getattr(
            prefs,
            "user_preferences",
            ", ".join(prefs.interests) if prefs.interests else "",
        )
        include_narration = (
            True if location.is_narration is None else bool(location.is_narration)
        )
        photo_count = 2 if location.include_photos is None else int(location.include_photos)

        return NarrationSettings(
            latitude=location.lat,
            longitude=location.lng,
            detail_level=NarrationDetailLevel(detail_level),
            search_radius=getattr(
                prefs,
                "search_radius",
                defaults.default_search_radius,
            ),
            language=NarrationLanguage(
                language_name=language_name,
                language_tag=language_tag,
            ),
            user_preferences=user_preferences,
            include_narration=include_narration,
            photo_count=max(1, photo_count),
        )

    def build_narration_message(self, narration: NarrationResult) -> NarrationMessage:
        return NarrationMessage(text=narration.narration)

    def build_pois_message_many(
        self,
        pois: list[tuple[PoiCandidate, list[str]]],
    ) -> PoisMessage:
        return PoisMessage(
            data=[
                Poi(
                    name=poi.name,
                    photos=photos,
                    desc=poi.description,
                    lat=poi.lat,
                    lng=poi.lon,
                )
                for poi, photos in pois
            ]
        )

    def build_pois_message(
        self,
        poi: PoiCandidate,
        photos: list[str],
    ) -> PoisMessage:
        return PoisMessage(
            data=[
                Poi(
                    name=poi.name,
                    photos=photos,
                    desc=poi.name,
                    lat=poi.lat,
                    lng=poi.lon,
                )
            ]
        )
