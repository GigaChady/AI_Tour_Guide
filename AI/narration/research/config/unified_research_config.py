from dataclasses import dataclass


@dataclass(frozen=True)
class UnifiedResearchConfig:
    """Limits for the notebook's single-conversation GLM experiment."""

    max_model_rounds: int = 5
    max_tool_calls: int = 12
    max_tokens: int = 6_000
    request_timeout_seconds: int = 600
    temperature: float = 0.1
    top_p: float = 0.9
    reasoning_effort: str = "low"
    clear_thinking: bool = True

    def __post_init__(self) -> None:
        if (self.max_model_rounds <= 0 or self.max_tool_calls <= 0
                or self.max_tokens <= 0 or self.request_timeout_seconds <= 0
                or not 0 <= self.temperature <= 1 or not 0 < self.top_p <= 1):
            raise ValueError("Invalid unified research experiment configuration")
