from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaFilteringConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FILTERING_OLLAMA_",
        case_sensitive=False,
        extra="ignore",
    )

    base_url: str = "http://ollama:11434"
    model_name: str = "mistral-nemo"
    temperature: float = Field(default=0.05, ge=0.0, le=1.0)
    top_k: int = 20
    top_p: float = Field(default=0.7, ge=0.0, le=1.0)
    num_predict: int = 256


class OllamaNarrationConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NARRATIVE_OLLAMA_",
        case_sensitive=False,
        extra="ignore",
    )

    base_url: str = "http://ollama:11434"
    model_name: str = "mistral-nemo"
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    top_k: int = 30
    top_p: float = Field(default=0.8, ge=0.0, le=1.0)
    num_predict: int = 512
    format: str = "json"
    repeat_penalty: float = Field(default=1.1, ge=1.0)
