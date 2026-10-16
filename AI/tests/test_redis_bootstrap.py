import pytest

from app_config import AppConfig
from bootstrap import build_redis_narration_worker
from workers.redis_narration.redis_stream_worker import RedisStreamWorker


def test_mock_redis_transport_remains_available_without_live_pipeline():
    worker = build_redis_narration_worker(AppConfig(ai_mock=True))
    assert isinstance(worker, RedisStreamWorker)
    assert worker.event_handler.mock_enabled is True


def test_live_redis_transport_fails_before_consuming_events_without_new_pipeline():
    with pytest.raises(RuntimeError, match="not connected to Redis"):
        build_redis_narration_worker(AppConfig(ai_mock=False))
