from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NominatimConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOMINATIM_",
        case_sensitive=False,
        extra="ignore",
    )

    user_agent: str = "AI-Tour-Guide/0.1 (contact: unavailable)"
    timeout_seconds: int = Field(default=10, ge=1)
