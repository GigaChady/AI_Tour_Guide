from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NvidiaConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLOUD_NARRATIVE_",
        case_sensitive=False,
        extra="ignore",
    )

    model_name: str = "meta/llama-4-maverick-17b-128e-instruct"
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=700, ge=1)
    request_timeout_seconds: int = Field(default=45, ge=1)
    max_retries: int = Field(default=2, ge=0)
    retry_backoff_seconds: float = Field(default=2.0, ge=0.0)
