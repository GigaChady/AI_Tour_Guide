from __future__ import annotations

import json
import logging
import time
import uuid

import redis

from workers.redis_narration.config.redis_config import RedisWorkerConfig
from workers.redis_narration.messages import WorkerResult
from workers.redis_narration.narration_event_handler import NarrationEventHandler

logger = logging.getLogger(__name__)


class RedisStreamWorker:
    def __init__(
        self,
        event_handler: NarrationEventHandler,
        client: redis.Redis | None = None,
        config: RedisWorkerConfig | None = None,
    ):
        self.config = config or RedisWorkerConfig()
        self.event_handler = event_handler
        self.client = client or redis.from_url(
            self.config.redis_url,
            decode_responses=True,
            socket_timeout=self.config.block_ms / 1000 + 5,
        )
        self.last_id = self.config.start_id

    def _read_batch(self):
        response = self.client.xread(
            {self.config.stream_key: self.last_id},
            count=self.config.count,
            block=self.config.block_ms,
        )
        if not response:
            return []
        return [entry for _, entries in response for entry in entries]

    def _publish(self, result: WorkerResult) -> None:
        if result.pois is None:
            logger.info("No POIs generated for session %s", result.session_id)
            return

        channel = f"{self.config.pubsub_prefix}{result.session_id}"
        narration_id = str(uuid.uuid4())
        poi_data = result.pois.model_dump()
        poi_data["narration_id"] = narration_id
        self.client.publish(channel, json.dumps(poi_data, ensure_ascii=False))

        if result.narration is not None:
            narration_data = result.narration.model_dump()
            narration_data["narration_id"] = narration_id
            self.client.publish(
                channel,
                json.dumps(narration_data, ensure_ascii=False),
            )
        logger.info("Published stream event for session %s", result.session_id)

    def run(self) -> None:
        logger.info("Starting AI stream worker for %s", self.config.stream_key)
        while True:
            try:
                entries = self._read_batch()
                if not entries:
                    continue
                for entry_id, payload in entries:
                    try:
                        prefs_json = self.client.get(
                            f"{self.config.pref_cache}{payload.get('session_id', '')}"
                        )
                        preferences = json.loads(prefs_json) if prefs_json else {}
                        result = self.event_handler.handle(
                            entry_id,
                            payload,
                            preferences,
                        )
                        self._publish(result)
                    except Exception:
                        logger.exception("Failed to process stream event %s; skipping", entry_id)
                    finally:
                        self.last_id = entry_id
            except KeyboardInterrupt:
                logger.info("Stream worker stopped by user")
                return
            except Exception:
                logger.exception("Unhandled error in stream worker; retrying in 2s")
                time.sleep(2)
