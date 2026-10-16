from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ResearchBudgetExhausted(RuntimeError):
    """A provider stopped before issuing another external request."""


@dataclass(frozen=True)
class WikimediaArticle:
    title: str
    language: str
    url: str
    lead: str
    page_id: int | None = None
    wikidata_id: str = ""
    lat: float | None = None
    lon: float | None = None


class WikimediaArticleClient(Protocol):
    def find_article(
        self, name: str, *, disambiguator: str = ""
    ) -> WikimediaArticle | None: ...

    def fetch_sections(self, article: WikimediaArticle) -> str: ...

    @property
    def request_count(self) -> int: ...


@dataclass(frozen=True)
class WebSearchHit:
    title: str
    url: str
    snippet: str
    query: str


@dataclass(frozen=True)
class WebDocument:
    title: str
    url: str
    content: str


class WebResearchClient(Protocol):
    def search(self, query: str, *, max_results: int) -> list[WebSearchHit]: ...

    def extract(self, hit: WebSearchHit, *, max_chars: int) -> WebDocument: ...

    @property
    def request_count(self) -> int: ...


class ResearchLanguageModel(Protocol):
    def generate(self, messages: list[tuple[str, str]]) -> str: ...
