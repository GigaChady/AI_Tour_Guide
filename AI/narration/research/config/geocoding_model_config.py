from dataclasses import dataclass


@dataclass(frozen=True)
class GeocodingModelConfig:
    model_name: str = "openai/gpt-oss-20b"
    temperature: float = 0.1
    top_p: float = 0.9
    max_tokens: int = 2_000
    reasoning_effort: str = "low"
    request_timeout_seconds: int = 600

    def __post_init__(self) -> None:
        if (not self.model_name.strip() or not 0 <= self.temperature <= 1
                or not 0 < self.top_p <= 1 or self.max_tokens <= 0
                or self.request_timeout_seconds <= 0):
            raise ValueError("Invalid geocoding model configuration")
