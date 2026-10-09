from __future__ import annotations


class NarrationPromptBuilder:
    def build_messages(
        self,
        location_name: str,
        location_info: str,
        user_preferences: str,
        language_name: str,
    ) -> list[tuple[str, str]]:
        system_prompt = (
            "You are a tourist guide. Your task is to create a narration about the given place.\n"
            "RULES:\n"
            "1. Use the provided facts, but present them in an interesting and engaging way.\n"
            "2. Adapt the narration to the user's preferences.\n"
            "3. Return the result only as valid JSON with the fields: 'location' and 'narration'.\n"
            f"4. The narration must be written in the following language: {language_name}.\n"
            "5. Write the narration as a single line. Do not use newline characters.\n"
            "6. Do not include coordinates, URLs, raw links, exact street addresses, opening hours, ticket prices, or technical metadata.\n"
            "7. You may mention only the general city or region when it sounds natural.\n"
            "8. Do not add markdown, comments, explanations, Raw:, or any text outside the JSON."
        )

        user_prompt = (
            f"LOCATION: {location_name}\n"
            f"USER PREFERENCES: {user_preferences}\n"
            f"FACTS: {location_info}"
        )

        return [
            ("system", system_prompt),
            ("user", user_prompt),
        ]
