from __future__ import annotations

from typing import Any, Protocol

from narration.schemas import NarrationSettings


class LanguageModel(Protocol):
    def generate(self, messages: list[tuple[str, str]]) -> str: ...


class NarrativeGenerationAgent(Protocol):
    def generate_narration(
        self,
        location_name: str,
        location_info: str,
        narration_settings: NarrationSettings,
    ) -> dict[str, Any] | str: ...
