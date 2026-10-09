from __future__ import annotations

import logging
import random
import time

import requests
from requests import Session

from integrations.poi.overpass.config import OverpassConfig
from integrations.poi.overpass.overpass_models import OverpassResponse

logger = logging.getLogger(__name__)


class OverpassClient:
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        user_agent: str | None = None,
        config: OverpassConfig | None = None,
        servers: list[str] | None = None,
        session: Session | None = None,
    ):
        self.config = config or OverpassConfig()
        self.servers = servers or self.config.servers
        self.session = session or Session()
        self.session.headers.update(
            {"User-Agent": user_agent or "AI-Tour-Guide/0.1 (contact: unavailable)"}
        )

    def get_nearby_poi_data(
        self,
        lat: float,
        lon: float,
        radius: int = 50,
    ) -> OverpassResponse | None:
        query = self._build_query(lat, lon, radius)

        for url in self.servers:
            data = self._request(
                url=url,
                query=query,
            )

            if data is not None:
                return data

        logger.error("Could not get nearby POIs from any Overpass server")
        return None

    def _build_query(self, lat: float, lon: float, radius: int) -> str:
        return f"""
        [out:json][timeout:10];
        (
          node["tourism"](around:{radius},{lat},{lon});
          node["historic"](around:{radius},{lat},{lon});
          way["tourism"](around:{radius},{lat},{lon});
          way["historic"](around:{radius},{lat},{lon});
        );
        out center tags;
        """

    def _request(
        self,
        url: str,
        query: str,
        max_retries: int | None = None,
        timeout: int | None = None,
    ) -> OverpassResponse | None:
        max_retries = self.config.max_retries if max_retries is None else max_retries
        timeout = self.config.timeout_seconds if timeout is None else timeout
        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    "Requesting Overpass server=%s attempt=%s/%s",
                    url,
                    attempt + 1,
                    max_retries + 1,
                )

                response = self.session.post(
                    url,
                    data={"data": query},
                    timeout=timeout,
                )

                logger.info(
                    "Overpass response server=%s status=%s",
                    url,
                    response.status_code,
                )

                if response.status_code == 200:
                    return OverpassResponse.model_validate(response.json())

                if response.status_code not in self.RETRYABLE_STATUS_CODES:
                    logger.warning(
                        "Non-retryable Overpass response from %s: HTTP %s, body=%s",
                        url,
                        response.status_code,
                        response.text[:300],
                    )
                    return None

                self._sleep_before_retry(response=response, attempt=attempt, url=url)

            except requests.exceptions.Timeout:
                self._sleep_after_exception("Overpass timeout from %s", url, attempt)

            except requests.exceptions.RequestException as e:
                self._sleep_after_exception(
                    "Overpass request error from %s: " + str(e),
                    url,
                    attempt,
                )

            except ValueError as e:
                logger.warning("Invalid JSON from Overpass server %s: %s", url, e)
                return None

        return None

    def _sleep_before_retry(
        self,
        response: requests.Response,
        attempt: int,
        url: str,
    ) -> None:
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            sleep_seconds = int(retry_after)
        else:
            sleep_seconds = self._retry_sleep_seconds(attempt)

        logger.warning(
            "Retryable Overpass response from %s: HTTP %s. Sleeping %.2fs",
            url,
            response.status_code,
            sleep_seconds,
        )
        time.sleep(sleep_seconds)

    def _sleep_after_exception(self, message: str, url: str, attempt: int) -> None:
        sleep_seconds = self._retry_sleep_seconds(attempt)
        logger.warning(message + ". Sleeping %.2fs", url, sleep_seconds)
        time.sleep(sleep_seconds)

    @staticmethod
    def _retry_sleep_seconds(attempt: int) -> float:
        return min(2 ** attempt, 8) + random.uniform(0, 0.5)
