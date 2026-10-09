import logging

from narration.narration_generation.contracts import LanguageModel
from narration.narration_generation.parsers.narration_response_parser import NarrationResponseParser
from narration.narration_generation.prompts.narration_prompt_builder import NarrationPromptBuilder
from narration.schemas import NarrationSettings


class CloudNarrativeAgent:
    def __init__(
        self,
        model: LanguageModel,
        prompt_builder: NarrationPromptBuilder | None = None,
        response_parser: NarrationResponseParser | None = None,
    ):
        self.model = model
        self.prompt_builder = prompt_builder or NarrationPromptBuilder()
        self.response_parser = response_parser or NarrationResponseParser()

    def generate_narration(
        self,
        location_name: str,
        location_info: str,
        narration_settings: NarrationSettings,
    ):
        logging.info("Starting narration generation about: %s", location_name)
        messages = self.prompt_builder.build_messages(
            location_name=location_name,
            location_info=location_info,
            user_preferences=narration_settings.user_preferences,
            language_name=narration_settings.language.language_name,
        )
        response = self.model.generate(messages)
        logging.info("Finished narration generation")
        return self.response_parser.parse(response)
