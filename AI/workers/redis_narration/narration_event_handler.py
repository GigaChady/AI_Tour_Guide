from __future__ import annotations

import logging
import os

from narration.pipeline import TourNarrationPipeline
from narration.schemas import NarrationPipelineRequest, PoiCandidate
from photos.contracts import PhotoGenerator
from workers.redis_narration.backend_message_mapper import BackendMessageMapper
from workers.redis_narration.messages import (
    LocationEvent,
    PreferencesEvent,
    WorkerResult,
)

logger = logging.getLogger(__name__)


class NarrationEventHandler:
    def __init__(
        self,
        pipeline: TourNarrationPipeline | None,
        photo_processor: PhotoGenerator | None = None,
        message_mapper: BackendMessageMapper | None = None,
        mock_enabled: bool | None = None,
    ):
        self.pipeline = pipeline
        self.photo_processor = photo_processor
        self.message_mapper = message_mapper or BackendMessageMapper()
        self.mock_enabled = (
            mock_enabled
            if mock_enabled is not None
            else os.getenv("AI_MOCK", "false").lower() in ("true", "1", "t")
        )

    def handle(
        self,
        entry_id: str,
        payload: dict,
        preferences: dict | None,
    ) -> WorkerResult:
        try:
            event = LocationEvent.model_validate(payload)
        except Exception as exc:
            raise ValueError(
                f"Invalid backend stream payload for entry {entry_id}"
            ) from exc

        try:
            prefs = PreferencesEvent.model_validate(preferences or {})
        except Exception as exc:
            raise ValueError("Invalid preferences cache") from exc

        if self.mock_enabled:
            return self._mock_result(event, prefs)
        if self.pipeline is None:
            raise RuntimeError("Narration pipeline is not configured")

        settings = self.message_mapper.build_narration_settings(event, prefs)
        result = self.pipeline.run(
            NarrationPipelineRequest(
                session_id=event.session_id,
                settings=settings,
            )
        )

        if result.selected_pois:
            pois = [
                (
                    selected.poi,
                    self._generate_photo_urls(selected.poi, settings.photo_count),
                )
                for selected in result.selected_pois
            ]
            return WorkerResult(
                session_id=event.session_id,
                pois=self.message_mapper.build_pois_message_many(pois),
            )

        if result.poi is None:
            return WorkerResult(session_id=event.session_id)

        pois_message = self.message_mapper.build_pois_message(
            result.poi,
            self._generate_photo_urls(result.poi, settings.photo_count),
        )
        narration_message = (
            self.message_mapper.build_narration_message(result.narration)
            if result.narration
            else None
        )
        return WorkerResult(
            session_id=event.session_id,
            narration=narration_message,
            pois=pois_message,
        )

    def _mock_result(
        self,
        event: LocationEvent,
        preferences: PreferencesEvent,
    ) -> WorkerResult:
        from workers.redis_narration.mocks.responses import mock_narration, mock_pois

        pois = mock_pois(event.session_id, event.lat, event.lng)
        narration = mock_narration(
            event.session_id,
            preferences,
            event.lat,
            event.lng,
            pois,
        )
        from workers.redis_narration.messages import PoisMessage

        return WorkerResult(
            session_id=event.session_id,
            narration=narration,
            pois=PoisMessage(data=pois),
        )

    def _generate_photo_urls(
        self,
        poi: PoiCandidate,
        photo_count: int,
    ) -> list[str]:
        if self.photo_processor is None:
            return []
        urls = []
        for index in range(max(0, photo_count)):
            url = self.photo_processor.generate(poi.category, index)
            if url:
                urls.append(url)
        return urls
