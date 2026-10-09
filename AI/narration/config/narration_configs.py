from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from narration.schemas import NarrationDetailLevel, NarrationLanguage


class NarrationDefaultsConfig(BaseSettings):
    """Global defaults used to translate worker events into pipeline settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    default_detail_level: NarrationDetailLevel = Field(
        default=NarrationDetailLevel.DETAILED,
    )
    default_search_radius: int = Field(default=2500, ge=1)
    default_language: str = "pl"
    default_language_name: str = "Polish"
    max_narration_length: int = Field(default=500, ge=1)

    @property
    def default_language_config(self) -> NarrationLanguage:
        return NarrationLanguage(
            language_name=self.default_language_name,
            language_tag=self.default_language,
        )
