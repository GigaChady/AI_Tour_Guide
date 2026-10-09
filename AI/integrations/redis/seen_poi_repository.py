from narration.poi_selection.config import PoiSelectionConfig


class RedisSeenPoiRepository:
    def __init__(self, redis_client, config: PoiSelectionConfig | None = None):
        self.redis_client = redis_client
        self.config = config or PoiSelectionConfig()

    def get_seen(self, session_id: str) -> set[str]:
        return set(self.redis_client.smembers(self._key(session_id)))

    def mark_seen(self, session_id: str, poi_name: str) -> None:
        key = self._key(session_id)
        self.redis_client.sadd(key, poi_name)
        self.redis_client.expire(key, self.config.seen_ttl_seconds)

    def _key(self, session_id: str) -> str:
        return f"{self.config.seen_key_prefix}{session_id}"
