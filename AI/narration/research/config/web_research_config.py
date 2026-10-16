from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebResearchConfig:
    """Budgets and output limits for one web-research run."""

    max_search_calls: int = 3
    max_results_per_search: int = 5
    max_extract_attempts: int = 4
    max_successful_documents: int = 2
    max_document_chars: int = 7_000
    max_total_chunks: int = 6
    min_chunk_chars: int = 50
    max_chunk_chars: int = 700
    max_anchor_chars: int = 150
    max_topic_chars: int = 100
    max_aliases: int = 5
    max_location_name_chars: int = 150
    area_title_weight: int = 6
    area_snippet_weight: int = 3
    city_title_weight: int = 4
    city_snippet_weight: int = 2
    street_title_weight: int = 2
    street_snippet_weight: int = 1
    explicit_street_title_bonus: int = 3
    explicit_street_snippet_bonus: int = 2
    repeated_query_penalty: int = 2

    def __post_init__(self) -> None:
        if any(value <= 0 for value in vars(self).values()):
            raise ValueError("Research limits and ranking weights must be positive")
        if self.max_results_per_search > 8 or self.max_document_chars > 12_000:
            raise ValueError("Research provider limit exceeded")
        if self.max_successful_documents > self.max_extract_attempts:
            raise ValueError("Successful documents cannot exceed extraction attempts")
        if self.min_chunk_chars > self.max_chunk_chars:
            raise ValueError("Minimum chunk length exceeds maximum")

    @property
    def max_provider_requests(self) -> int:
        return self.max_search_calls + self.max_extract_attempts
