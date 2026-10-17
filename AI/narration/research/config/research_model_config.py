from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchModelConfig:
    temperature: float = 0.1
    max_tokens: int = 4_000
    reasoning_effort: str = "low"
    request_timeout_seconds: int = 600
    max_retries: int = 0
    diagnostic_preview_chars: int = 1_000
    chunk_preview_chars: int = 140
