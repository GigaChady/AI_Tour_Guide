from __future__ import annotations

from typing import Protocol

from narration.schemas import EnrichedPoi, NarrationSettings


class InformationFilteringAgent(Protocol):
    def filter_information(
        self,
        enriched_poi: EnrichedPoi,
        narration_settings: NarrationSettings,
    ) -> str: ...


class InformationFilteringModel(Protocol):
    def generate(self, messages: list[tuple[str, str]]) -> str: ...
