from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import requests

from experiments.tool_calling.contracts import LocationContext, SearchResult, StoreResult
from experiments.tool_calling.geo_provider import GeoProvider
from experiments.tool_calling.knowledge_store import InMemoryKnowledgeStore


@dataclass
class GroundedResearchRun:
    location: LocationContext
    answer: str
    search_queries: list[str]
    cited_facts: list[dict[str, Any]]
    store_result: StoreResult
    usage: dict[str, Any] = field(default_factory=dict)
    latency_s: float = 0.0


class GeminiGroundedResearch:
    """Research an area with Gemini Search grounding and save cited answer segments."""

    def __init__(
        self,
        api_key: str,
        geo: GeoProvider,
        store: InMemoryKnowledgeStore,
        *,
        model: str = "gemini-2.5-flash",
        timeout_seconds: int = 180,
    ):
        if not api_key.strip():
            raise ValueError("Set GEMINI_API_KEY before running the experiment")
        self.api_key = api_key.strip()
        self.geo = geo
        self.store = store
        self.model = model
        self.timeout_seconds = timeout_seconds

    def run(self, lat: float, lon: float) -> GroundedResearchRun:
        started = time.perf_counter()
        location = self.geo.reverse_geocode(lat, lon)
        area_name = location.neighbourhood or location.district or location.city
        place = ", ".join(
            part for part in [location.street, area_name, location.city, location.country]
            if part
        )
        prompt = (
            f"Zbadaj ciekawe dla turysty fakty o okolicy: {place}. "
            f"Współrzędne orientacyjne: {lat}, {lon}. "
            "Użyj Google Search. Podaj 4–8 krótkich punktów po polsku. "
            "Każdy punkt ma zawierać dokładnie jeden konkretny fakt o lokalnej historii, "
            "architekturze, kulturze albo miejscu w tej okolicy. "
            "Opieraj się na znalezionych źródłach lokalnych i miejskich. "
            "Pomiń fakty, których źródła nie potwierdzają. "
            "Nie dodawaj wstępu ani podsumowania."
        )
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        response = requests.post(
            url,
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.1},
            },
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            detail = response.text[:2000]
            if response.status_code in {403, 404}:
                detail += (
                    " Model Gemini 2.5 Flash może być niedostępny dla nowych kont; "
                    "sprawdź dostęp modeli w Google AI Studio."
                )
            raise RuntimeError(f"Gemini API HTTP {response.status_code}: {detail}")

        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini API returned no candidates: {str(data)[:2000]}")
        candidate = candidates[0]
        answer = "\n".join(
            part.get("text", "")
            for part in candidate.get("content", {}).get("parts", [])
            if isinstance(part, dict) and part.get("text")
        )
        metadata = candidate.get("groundingMetadata") or {}
        query_list = metadata.get("webSearchQueries") or []
        search_queries = [str(query) for query in query_list]
        source_catalog = self._source_catalog(metadata, search_queries)
        chunks, cited_facts = self._grounded_chunks(metadata, source_catalog, area_name)

        if chunks:
            store_result = self.store.store_research(
                location,
                places=[],
                chunks=chunks,
                allowed_source_ids=set(source_catalog),
                source_catalog=source_catalog,
            )
        else:
            store_result = StoreResult(
                validation_errors=[
                    "Brak fragmentów odpowiedzi powiązanych przez Gemini ze źródłami; nic nie zapisano"
                ]
            )
        return GroundedResearchRun(
            location=location,
            answer=answer,
            search_queries=search_queries,
            cited_facts=cited_facts,
            store_result=store_result,
            usage=data.get("usageMetadata") or {},
            latency_s=time.perf_counter() - started,
        )

    @staticmethod
    def _source_catalog(
        metadata: dict[str, Any], search_queries: list[str]
    ) -> dict[str, SearchResult]:
        catalog: dict[str, SearchResult] = {}
        for index, chunk in enumerate(metadata.get("groundingChunks") or []):
            web = chunk.get("web") or {}
            uri = str(web.get("uri") or "")
            parsed = urlparse(uri)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            source_id = f"src_{index + 1:03d}"
            catalog[source_id] = SearchResult(
                source_id=source_id,
                title=str(web.get("title") or parsed.hostname),
                url=uri,
                snippet="",
                query=" | ".join(search_queries),
            )
        return catalog

    @staticmethod
    def _grounded_chunks(
        metadata: dict[str, Any],
        catalog: dict[str, SearchResult],
        area_name: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        chunks: list[dict[str, Any]] = []
        cited_facts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for support in metadata.get("groundingSupports") or []:
            segment = support.get("segment") or {}
            content = str(segment.get("text") or "").strip().lstrip("-• ")
            source_ids = sorted(
                {
                    f"src_{index + 1:03d}"
                    for index in support.get("groundingChunkIndices") or []
                    if isinstance(index, int) and f"src_{index + 1:03d}" in catalog
                }
            )
            if len(content) < 25 or not source_ids or content.casefold() in seen:
                continue
            seen.add(content.casefold())
            chunks.append(
                {
                    "anchor_type": "AREA",
                    "anchor_name": area_name,
                    "canonical_name": area_name,
                    "topic": "local_fact",
                    "content": content,
                    "source_ids": source_ids,
                    "confidence": 0.6,
                }
            )
            cited_facts.append(
                {
                    "content": content,
                    "sources": [catalog[source_id].to_dict() for source_id in source_ids],
                }
            )
        return chunks, cited_facts
