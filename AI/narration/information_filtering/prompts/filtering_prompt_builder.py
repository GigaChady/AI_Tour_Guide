from __future__ import annotations


class FilteringPromptBuilder:
    def build_messages(
        self,
        poi_name: str,
        raw_text: str,
        user_preferences: str,
    ) -> list[tuple[str, str]]:
        system_prompt = (
            "Twoim zadaniem jest wyciagniecie z tekstu wylacznie istotnych faktow "
            "i informacji o podanym miejscu.\n"
            "ZASADY:\n"
            "1. Usun informacje o cenach biletow, godzinach otwarcia i linkach.\n"
            "2. Jesli podano preferencje, szukaj informacji, ktore do nich pasuja.\n"
            "3. Zwroc liste punktowa w jezyku polskim."
        )

        user_prompt = (
            f"MIEJSCE: {poi_name}\n"
            f"PREFERENCJE: {user_preferences}\n"
            f"TEKST:\n{raw_text}"
        )

        return [
            ("system", system_prompt),
            ("user", user_prompt),
        ]

    def build_cloud_prompt(
        self,
        poi_name: str,
        poi_description: str | None,
        user_preferences: str | None,
        include_prompt: bool,
    ) -> str:
        description = (poi_description or "").strip() or "No POI description provided."
        preferences = (user_preferences or "").strip()

        if include_prompt is False:
            prompt = (
                f"POI name: {poi_name}\n"
                f"POI context:\n{description}"
            )
            if preferences:
                prompt += f"\nUser preferences: {preferences}"
            return prompt

        preference_instruction = (
            f"\nUser preferences: {preferences}" if preferences else ""
        )
        return (
            "You are preparing a cloud filtering prompt for a travel narration pipeline.\n"
            f"POI name: {poi_name.strip()}\n"
            f"POI description: {description}"
            f"{preference_instruction}\n"
            "Compose a concise English prompt that keeps only the most relevant factual details for this POI. "
            "Do not include coordinates, URLs, raw links, exact street addresses, ticket prices, opening hours, or technical metadata."
        )
