from __future__ import annotations

import redis as redis_lib

from app_config import AppConfig
from integrations.geocoding.nominatim.nominatim_client import NominatimClient
from integrations.knowledge.wikimedia.wikimedia_search_client import WikimediaSearchClient
from integrations.llm.nvidia.nvidia_language_model import NvidiaLanguageModel
from integrations.poi.overpass.overpass_client import OverpassClient
from integrations.poi.overpass.overpass_poi_parser import OverpassPoiParser
from integrations.redis import RedisSeenPoiRepository
from integrations.storage.minio.minio_image_storage import MinioImageStorage
from narration.information_filtering.agents import CloudNarrationContextAgent
from narration.narration_generation.agents import CloudNarrativeAgent
from narration.pipeline import TourNarrationPipeline
from narration.poi_selection.config import PoiSelectionConfig
from photos import PhotoProcessor
from workers.redis_narration.backend_message_mapper import BackendMessageMapper
from workers.redis_narration.config import RedisWorkerConfig
from workers.redis_narration.narration_event_handler import NarrationEventHandler
from workers.redis_narration.redis_stream_worker import RedisStreamWorker


def create_redis_client(config: RedisWorkerConfig):
    return redis_lib.from_url(
        config.redis_url,
        decode_responses=True,
        socket_timeout=config.block_ms / 1000 + 5,
    )


def build_narration_pipeline(
    *,
    redis_client=None,
) -> TourNarrationPipeline:
    selection_config = PoiSelectionConfig()
    seen_repository = (
        RedisSeenPoiRepository(redis_client, selection_config)
        if redis_client is not None
        else None
    )
    return TourNarrationPipeline.default(
        geocoding_client=NominatimClient(),
        poi_data_client=OverpassClient(),
        poi_parser=OverpassPoiParser(),
        search_client=WikimediaSearchClient(),
        filtering_agent=CloudNarrationContextAgent(),
        narrative_generation_agent=CloudNarrativeAgent(
            model=NvidiaLanguageModel(),
        ),
        seen_poi_repository=seen_repository,
        poi_selection_config=selection_config,
    )


def build_redis_narration_worker(
    app_config: AppConfig | None = None,
) -> RedisStreamWorker:
    app_config = app_config or AppConfig()
    worker_config = RedisWorkerConfig()
    redis_client = create_redis_client(worker_config)

    pipeline = None
    photo_processor = None
    if not app_config.ai_mock:
        pipeline = build_narration_pipeline(redis_client=redis_client)
        photo_processor = PhotoProcessor(MinioImageStorage())

    handler = NarrationEventHandler(
        pipeline=pipeline,
        photo_processor=photo_processor,
        message_mapper=BackendMessageMapper(),
        mock_enabled=app_config.ai_mock,
    )
    return RedisStreamWorker(
        event_handler=handler,
        client=redis_client,
        config=worker_config,
    )
