from __future__ import annotations

from typing import Callable
from urllib.parse import urlsplit

import requests

from integrations.knowledge.tavily.config import TavilyResearchConfig
from integrations.knowledge.tavily.markdown_cleanup import clean_extracted_markdown

from narration.research.contracts import ResearchBudgetExhausted, WebDocument, WebSearchHit


class TavilyResearchClient:
    """Small Search/Extract adapter; only search results can be extracted."""

    def __init__(
        self,
        *,
        api_key: str = "",
        search_depth: str | None = None,
        timeout_seconds: int | None = None,
        max_requests: int | None = None,
        session: requests.Session | None = None,
        on_extract_raw_content: Callable[[str, str, int], None] | None = None,
        config: TavilyResearchConfig | None = None,
    ):
        self.config = config or TavilyResearchConfig()
        search_depth = search_depth or self.config.search_depth
        timeout_seconds = timeout_seconds if timeout_seconds is not None else self.config.timeout_seconds
        max_requests = max_requests if max_requests is not None else self.config.max_requests
        if search_depth not in {"basic", "advanced", "fast", "ultra-fast"}:
            raise ValueError("Unsupported Tavily search depth")
        if timeout_seconds <= 0 or max_requests <= 0:
            raise ValueError("Tavily limits must be positive")
        self.api_key = api_key.strip()
        self.search_depth = search_depth
        self.timeout_seconds = timeout_seconds
        self.max_requests = max_requests
        self.session = session or requests.Session()
        self.on_extract_raw_content = on_extract_raw_content
        self.request_count = 0
        self._seen_urls: set[str] = set()

    def search(self, query: str, *, max_results: int | None = None) -> list[WebSearchHit]:
        query = query.strip()
        max_results = max_results if max_results is not None else self.config.max_results
        if not query:
            raise ValueError("Search query cannot be empty")
        if not 1 <= max_results <= self.config.max_results:
            raise ValueError(f"max_results must be between 1 and {self.config.max_results}")
        data = self._post("search", {
            "query": query,
            "search_depth": self.search_depth,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        })
        hits: list[WebSearchHit] = []
        for row in data.get("results") or []:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            hit = WebSearchHit(
                title=str(row.get("title") or url),
                url=url,
                snippet=str(row.get("content") or ""),
                query=query,
            )
            hits.append(hit)
            self._seen_urls.add(url)
        return hits

    def extract(self, hit: WebSearchHit, *, max_chars: int | None = None) -> WebDocument:
        max_chars = max_chars if max_chars is not None else self.config.max_extract_chars
        if hit.url not in self._seen_urls:
            raise ValueError("Only a URL returned by search may be extracted")
        if not 1 <= max_chars <= self.config.max_extract_chars:
            raise ValueError(f"max_chars must be between 1 and {self.config.max_extract_chars}")
        data = self._post("extract", {
            "urls": [hit.url],
            "extract_depth": self.config.extract_depth,
            "format": self.config.extract_format,
        })
        raw_content = ""
        for row in data.get("results") or []:
            if isinstance(row, dict) and row.get("url") == hit.url:
                raw_content = str(row.get("raw_content") or "")
                if raw_content.strip():
                    break
        if self.on_extract_raw_content is not None:
            self.on_extract_raw_content(hit.url, raw_content, max_chars)
        content = clean_extracted_markdown(raw_content)
        if content:
            return WebDocument(hit.title, hit.url, content[:max_chars])
        raise RuntimeError(f"Tavily Extract returned no content for {hit.url}")

    def _post(self, endpoint: str, payload: dict) -> dict:
        if self.request_count >= self.max_requests:
            raise ResearchBudgetExhausted("Tavily request budget exhausted")
        self.request_count += 1
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            # Experimental keyless access used by the existing notebook adapter.
            headers["X-Tavily-Access-Mode"] = "keyless"
        response = self.session.post(
            f"https://api.tavily.com/{endpoint}",
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Invalid Tavily response")
        if data.get("error"):
            raise RuntimeError(f"Tavily {endpoint} failed: {data['error']}")
        return data
