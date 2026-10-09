import logging

from narration.information_filtering.contracts import InformationFilteringModel
from narration.information_filtering.prompts.filtering_prompt_builder import FilteringPromptBuilder
from narration.schemas import EnrichedPoi, NarrationSettings


class FilteringAgent:
    """LLM-backed alternative for the context preparation step."""

    def __init__(
        self,
        model: InformationFilteringModel,
        prompt_builder: FilteringPromptBuilder | None = None,
    ):
        self.model = model
        self.prompt_builder = prompt_builder or FilteringPromptBuilder()

    def filter_information(
        self,
        enriched_poi: EnrichedPoi,
        narration_settings: NarrationSettings,
    ) -> str:
        logging.info("Starting information filtering")
        messages = self.prompt_builder.build_messages(
            poi_name=enriched_poi.poi.name,
            raw_text=enriched_poi.to_context_text(),
            user_preferences=narration_settings.user_preferences,
        )
        result = self.model.generate(messages)
        logging.info("Finished information filtering")
        return result
