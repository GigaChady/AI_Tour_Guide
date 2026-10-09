from __future__ import annotations

import json
import logging
import re
from typing import Any

try:
    from unidecode import unidecode
except ImportError:
    def unidecode(value: str) -> str:
        return value

logger = logging.getLogger(__name__)


class NarrationResponseParser:
    def parse(self, content: str) -> dict[str, Any] | str:
        result = self._parse_json_with_recovery(content)
        if result is None:
            logger.error("Invalid narration response. Could not recover valid JSON")
            logger.error("Raw response: %s", content)
            return unidecode(self._decode_unicode_escapes(content))

        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, str):
                    result[key] = unidecode(self._decode_unicode_escapes(value))

        logger.info("Narration with ASCII conversion: %s", result)
        return result

    def _parse_json_with_recovery(self, content: str) -> Any | None:
        candidates = self._json_candidates(content)
        for candidate in candidates:
            try:
                result = json.loads(candidate)
            except json.JSONDecodeError as e:
                logger.debug("Narration JSON candidate failed: %s", e)
                continue

            if isinstance(result, str):
                nested = result.strip()
                if nested != candidate and self._looks_like_json(nested):
                    try:
                        return json.loads(nested)
                    except json.JSONDecodeError as e:
                        logger.debug("Nested narration JSON candidate failed: %s", e)

            return result

        return None

    def _json_candidates(self, content: str) -> list[str]:
        stripped = content.strip()
        candidates = [stripped]

        without_fence = self._strip_markdown_fence(stripped)
        if without_fence != stripped:
            candidates.append(without_fence)

        for value in (stripped, without_fence):
            extracted = self._extract_json_object(value)
            if extracted and extracted != value:
                candidates.append(extracted)

        unique_candidates = []
        for candidate in candidates:
            if candidate and candidate not in unique_candidates:
                unique_candidates.append(candidate)
        return unique_candidates

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        return re.sub(
            r"^```(?:json)?\s*(.*?)\s*```$",
            r"\1",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

    @staticmethod
    def _extract_json_object(content: str) -> str | None:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return content[start : end + 1].strip()

    @staticmethod
    def _looks_like_json(content: str) -> bool:
        return content.startswith("{") or content.startswith("[")

    @staticmethod
    def _decode_unicode_escapes(content: str) -> str:
        return re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda match: chr(int(match.group(1), 16)),
            content,
        )
