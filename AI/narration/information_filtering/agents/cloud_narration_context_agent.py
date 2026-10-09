import logging

from narration.information_filtering.config import FilteringConfig
from narration.information_filtering.prompts.filtering_prompt_builder import FilteringPromptBuilder
from narration.schemas import EnrichedPoi, NarrationSettings

logger = logging.getLogger(__name__)


class CloudNarrationContextAgent:
    """Prepare factual context without making an additional LLM request."""

    def __init__(
        self,
        config: FilteringConfig | None = None,
        prompt_builder: FilteringPromptBuilder | None = None,
    ):
        self.config = config or FilteringConfig()
        self.prompt_builder = prompt_builder or FilteringPromptBuilder()

    def build_context(
        self,
        poi_name: str,
        poi_description: str | None = None,
        user_preferences: str | None = None,
    ) -> str:
        return self.prompt_builder.build_cloud_prompt(
            poi_name=poi_name,
            poi_description=poi_description,
            user_preferences=user_preferences,
            include_prompt=self.config.include_prompt,
        )

    def filter_information(
        self,
        enriched_poi: EnrichedPoi,
        narration_settings: NarrationSettings,
    ) -> str:
        return self.build_context(
            poi_name=enriched_poi.poi.name,
            poi_description=enriched_poi.to_context_text(),
            user_preferences=narration_settings.user_preferences,
        )
