from dataclasses import dataclass


@dataclass(frozen=True)
class TavilyResearchConfig:
    search_depth: str = "basic"
    extract_depth: str = "basic"
    extract_format: str = "markdown"
    timeout_seconds: int = 20
    max_requests: int = 7
    max_results: int = 8
    max_extract_chars: int = 12_000

    def __post_init__(self) -> None:
        if self.search_depth not in {"basic", "advanced", "fast", "ultra-fast"}:
            raise ValueError("Unsupported Tavily search depth")
        if min(self.timeout_seconds, self.max_requests, self.max_results,
               self.max_extract_chars) <= 0:
            raise ValueError("Tavily limits must be positive")
        if self.max_results > 8 or self.max_extract_chars > 12_000:
            raise ValueError("Tavily provider limit exceeded")
