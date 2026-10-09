from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_servers() -> list[str]:
    return [
        "https://overpass.openstreetmap.fr/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://overpass.nchc.org.tw/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]


class OverpassConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OVERPASS_",
        case_sensitive=False,
        extra="ignore",
    )

    servers: list[str] = Field(default_factory=_default_servers)
    timeout_seconds: int = Field(default=12, ge=1)
    max_retries: int = Field(default=2, ge=0)
