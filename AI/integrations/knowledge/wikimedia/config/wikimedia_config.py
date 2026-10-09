from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WikimediaConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WIKIMEDIA_",
        case_sensitive=False,
        extra="ignore",
    )

    user_agent: str = "AI-Tour-Guide/0.1 (contact: unavailable)"
    timeout_seconds: int = Field(default=8, ge=1)
    languages: tuple[str, ...] = ("pl", "en", "de")
    max_extract_chars: int = Field(default=30000, ge=1)
