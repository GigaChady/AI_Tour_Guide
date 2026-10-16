from __future__ import annotations

import redis as redis_lib

from app_config import AppConfig
from workers.redis_narration.config import RedisWorkerConfig
from workers.redis_narration.narration_event_handler import (
    NarrationEventHandler,
    NarrationPipeline,
)
from workers.redis_narration.redis_stream_worker import RedisStreamWorker


def build_redis_narration_worker(
    app_config: AppConfig | None = None,
    *,
    pipeline: NarrationPipeline | None = None,
) -> RedisStreamWorker:
    app_config = app_config or AppConfig()
    if not app_config.ai_mock and pipeline is None:
        raise RuntimeError("The new narration pipeline is not connected to Redis yet")

    worker_config = RedisWorkerConfig()
    redis_client = redis_lib.from_url(
        worker_config.redis_url,
        decode_responses=True,
        socket_timeout=worker_config.block_ms / 1000 + 5,
    )
    return RedisStreamWorker(
        event_handler=NarrationEventHandler(pipeline=pipeline, mock_enabled=app_config.ai_mock),
        client=redis_client,
        config=worker_config,
    )
