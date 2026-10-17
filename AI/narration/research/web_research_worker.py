from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from narration.knowledge import (
    InMemoryKnowledgeStore,
    KnowledgeChunk,
    KnowledgeDraft,
    LocationContext,
    PlaceLocationResolver,
    PlaceAlias,
    PlaceCandidate,
    Scope,
    Source,
)
from narration.knowledge.tool_calling_place_locator import ToolCallingPlaceLocator
from narration.knowledge.normalization import normalized_name
from narration.research.config import WebResearchConfig
from narration.research.config.web_research_prompt import build_system_prompt
from narration.research.contracts import (
    ResearchBudgetExhausted,
    ResearchLanguageModel,
    WebDocument,
    WebResearchClient,
    WebSearchHit,
)


@dataclass(frozen=True)
class RankedSearchHit:
    url: str
    query: str
    score: int


@dataclass
class WebResearchRun:
    queries: list[str] = field(default_factory=list)
    ranked_hits: list[RankedSearchHit] = field(default_factory=list)
    extracted_urls: list[str] = field(default_factory=list)
    input_chars_by_url: dict[str, int] = field(default_factory=dict)
    model_response: str = ""
    chunk_ids: list[str] = field(default_factory=list)
    place_ids: list[str] = field(default_factory=list)
    unresolved_places: list[str] = field(default_factory=list)
    location_diagnostics: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    search_calls: int = 0
    extract_calls: int = 0
    llm_calls: int = 0
    api_request_count: int = 0
    new_chunk_count: int = 0
    matched_place_count: int = 0
    uncertain_place_count: int = 0
    latency_s: float = 0.0
    first_chunk_latency_s: float | None = None


class _Finding(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    scope: Scope
    anchor_name: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    content: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    street: str = ""
    city: str = ""
    address: str = ""


class _Findings(BaseModel):
    items: list[_Finding] = Field(default_factory=list)


@dataclass(frozen=True)
class _SearchCandidate:
    hit: WebSearchHit
    query_index: int
    result_index: int
    score: int


def _plain_text(markdown: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", markdown)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_findings(response: str) -> list[_Finding]:
    if not isinstance(response, str) or not response.strip():
        raise ValueError("Model returned no JSON content")
    text = response.strip()
    try:
        return _Findings.model_validate(json.loads(text)).items
    except (json.JSONDecodeError, ValidationError):
        pass

    # Some models wrap the final JSON in Markdown or explanatory text. Parse
    # complete JSON objects and use the last valid findings object.
    decoder = json.JSONDecoder()
    parsed: list[_Finding] | None = None
    for position, character in enumerate(text):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[position:])
            if isinstance(payload, dict) and "items" in payload:
                parsed = _Findings.model_validate(payload).items
        except (json.JSONDecodeError, ValidationError):
            continue
    if parsed is None:
        raise ValueError("Model response contains no valid findings JSON")
    return parsed


def _query_plan(location: LocationContext) -> list[str]:
    if not location.city:
        return []
    queries = []
    area = location.neighbourhood or location.district
    if area:
        queries.append(f'"{area}" "{location.city}" historia zabytki architektura')
    if location.street:
        street = re.sub(r"^(?:ulica|ul\.)\s+", "", location.street, flags=re.IGNORECASE)
        area_part = f' "{area}"' if area else ""
        queries.append(
            f'ulica "{street}" "{location.city}"{area_part} historia budynki'
        )
    queries.append(f'"{location.city}" {location.region} lokalna historia mniej znane miejsca')
    return list(dict.fromkeys(queries))


def _mentions(text: str, phrase: str) -> bool:
    key = normalized_name(phrase)
    return bool(key and f" {key} " in f" {text} ")


def _search_hit_score(
    hit: WebSearchHit, location: LocationContext, config: WebResearchConfig | None = None
) -> int:
    """Prioritize local search metadata without rejecting distant sources."""
    title = normalized_name(hit.title)
    snippet = normalized_name(hit.snippet)
    config = config or WebResearchConfig()
    area = location.neighbourhood or location.district
    street = re.sub(r"^(?:ulica|ul)\s+", "", normalized_name(location.street))
    score = 0
    for phrase, title_weight, snippet_weight in (
        (area, config.area_title_weight, config.area_snippet_weight),
        (location.city, config.city_title_weight, config.city_snippet_weight),
        (street, config.street_title_weight, config.street_snippet_weight),
    ):
        score += title_weight if _mentions(title, phrase) else 0
        score += snippet_weight if _mentions(snippet, phrase) else 0
    if street:
        score += config.explicit_street_title_bonus if _mentions(title, f"ulica {street}") else 0
        score += config.explicit_street_snippet_bonus if _mentions(snippet, f"ulica {street}") else 0
    return score


def _rank_search_hits(
    results: list[tuple[int, int, WebSearchHit]], location: LocationContext,
    config: WebResearchConfig | None = None,
) -> list[_SearchCandidate]:
    config = config or WebResearchConfig()
    by_url: dict[str, _SearchCandidate] = {}
    for query_index, result_index, hit in results:
        candidate = _SearchCandidate(
            hit=hit, query_index=query_index, result_index=result_index,
            score=_search_hit_score(hit, location, config),
        )
        existing = by_url.get(hit.url)
        if existing is None or (
            candidate.score, -candidate.query_index, -candidate.result_index
        ) > (existing.score, -existing.query_index, -existing.result_index):
            by_url[hit.url] = candidate

    pending = list(by_url.values())
    ordered: list[_SearchCandidate] = []
    used_queries: set[int] = set()
    while pending:
        chosen = max(pending, key=lambda item: (
            item.score - (config.repeated_query_penalty if item.query_index in used_queries else 0),
            item.score,
            not (urlsplit(item.hit.url).hostname or "").endswith(".wikipedia.org"),
            -item.query_index, -item.result_index,
        ))
        ordered.append(chosen)
        used_queries.add(chosen.query_index)
        pending.remove(chosen)
    return ordered


class WebResearchWorker:
    """Bounded, source-grounded web research shared by Tavily and future DDGS."""

    def __init__(
        self,
        *,
        provider_name: str,
        client: WebResearchClient,
        model: ResearchLanguageModel,
        store: InMemoryKnowledgeStore,
        place_locator: PlaceLocationResolver,
        tool_place_locator: ToolCallingPlaceLocator | None = None,
        config: WebResearchConfig | None = None,
    ):
        self.provider_name = provider_name
        self.client = client
        self.model = model
        self.store = store
        self.place_locator = place_locator
        self.tool_place_locator = tool_place_locator
        self.config = config or WebResearchConfig()

    def run(
        self,
        location: LocationContext,
        *,
        on_chunk: Callable[[KnowledgeChunk], None] | None = None,
    ) -> WebResearchRun:
        started = time.perf_counter()
        requests_before = self.client.request_count
        report = WebResearchRun()
        initial_chunk_ids = {chunk.chunk_id for chunk in self.store.chunks}
        search_results: list[tuple[int, int, WebSearchHit]] = []

        for query_index, query in enumerate(_query_plan(location)[:self.config.max_search_calls]):
            report.queries.append(query)
            report.search_calls += 1
            try:
                hits = self.client.search(query, max_results=self.config.max_results_per_search)
            except ResearchBudgetExhausted as exc:
                report.errors.append(str(exc))
                break
            except Exception as exc:
                report.errors.append(f"Search failed: {type(exc).__name__}: {exc}")
                continue
            search_results.extend(
                (query_index, result_index, hit)
                for result_index, hit in enumerate(hits)
            )

        ranked_hits = _rank_search_hits(search_results, location, self.config)
        report.ranked_hits = [
            RankedSearchHit(
                url=item.hit.url, query=report.queries[item.query_index], score=item.score
            )
            for item in ranked_hits
        ]
        documents: list[WebDocument] = []
        for item in ranked_hits:
            if (report.extract_calls >= self.config.max_extract_attempts
                    or len(documents) >= self.config.max_successful_documents):
                break
            hit = item.hit
            report.extract_calls += 1
            try:
                document = self.client.extract(hit, max_chars=self.config.max_document_chars)
            except ResearchBudgetExhausted as exc:
                report.errors.append(str(exc))
                break
            except Exception as exc:
                report.errors.append(f"Extract failed for {hit.url}: {type(exc).__name__}: {exc}")
                continue
            page_text = _plain_text(document.content)
            if not page_text:
                report.errors.append(f"Extracted text is empty for {document.url}")
                continue
            documents.append(WebDocument(document.title, document.url, page_text))
            report.extracted_urls.append(document.url)
            report.input_chars_by_url[document.url] = len(page_text)

        if documents:
            self._process_batch(location, documents, report, started, initial_chunk_ids, on_chunk)

        report.api_request_count = self.client.request_count - requests_before
        report.latency_s = time.perf_counter() - started
        return report

    def _process_batch(
        self,
        location: LocationContext,
        documents: list[WebDocument],
        report: WebResearchRun,
        started: float,
        initial_chunk_ids: set[str],
        on_chunk: Callable[[KnowledgeChunk], None] | None,
    ) -> None:
        sources = [self.store.add_source(Source.from_url(
            provider=self.provider_name, title=document.title, url=document.url,
            evidence_text=document.content,
        )) for document in documents]
        source_ids = [source.source_id for source in sources]
        combined_text = "\n\n".join(document.content for document in documents)
        report.llm_calls += 1
        response: str | None = None
        try:
            response = self.model.generate([
                ("system", build_system_prompt(self.config)),
                ("user", f"LOCATION: {location.model_dump_json()}\n"
                 f"RESEARCH TEXT:\n{combined_text}"),
            ])
            report.model_response = response
            findings = _parse_findings(response)
        except (ValueError, ValidationError, TypeError) as exc:
            preview = ""
            if isinstance(response, str) and response.strip():
                compact = re.sub(r"\s+", " ", response).strip()
                preview = f"; length={len(response)}, preview={compact[:160]!r}"
            report.errors.append(f"Invalid model output for research batch: {exc}{preview}")
            return
        except Exception as exc:
            report.errors.append(f"Model failed for research batch: {type(exc).__name__}: {exc}")
            return

        for finding in findings:
            if len(report.chunk_ids) >= self.config.max_total_chunks:
                break
            if not self._valid_finding_lengths(finding):
                report.errors.append(
                    f"Rejected finding outside configured field limits: {finding.anchor_name[:80]}"
                )
                continue
            if finding.scope != Scope.PLACE and not self._area_matches(
                finding.scope, normalized_name(finding.anchor_name), location
            ):
                report.errors.append(f"Rejected unrelated area: {finding.anchor_name}")
                continue

            place_id = None
            if finding.scope == Scope.PLACE:
                place_city = finding.city
                if not place_city:
                    report.unresolved_places.append(finding.anchor_name)
                    report.errors.append(
                        f"No city identified in research text for {finding.anchor_name}"
                    )
                    continue
                aliases = [
                    PlaceAlias(name=name, source_ids=source_ids)
                    for name in dict.fromkeys(finding.aliases)
                    if normalized_name(name)
                ]
                candidate = PlaceCandidate(
                    name=finding.anchor_name, city=place_city,
                    street=finding.street, address=finding.address, aliases=aliases,
                    source_ids=source_ids,
                )
                lookup_notes: list[str] = []
                geocoding_model_calls: list[int] = []
                try:
                    if self.tool_place_locator is not None:
                        candidate = self.tool_place_locator.resolve(
                            candidate, source_url="", source_text=combined_text,
                            research_location=location, description=finding.content,
                            diagnostics=lookup_notes, model_calls=geocoding_model_calls,
                        )
                    else:
                        candidate = self.place_locator.resolve(
                            candidate, source_url="", source_text=combined_text,
                            research_location=location, diagnostics=lookup_notes,
                        )
                    report.location_diagnostics[finding.anchor_name] = lookup_notes
                except Exception as exc:
                    report.location_diagnostics[finding.anchor_name] = lookup_notes
                    report.unresolved_places.append(finding.anchor_name)
                    report.errors.append(
                        f"Location lookup failed for {finding.anchor_name}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    continue
                finally:
                    report.llm_calls += len(geocoding_model_calls)
                if candidate is None:
                    report.unresolved_places.append(finding.anchor_name)
                    details = f" ({'; '.join(lookup_notes)})" if lookup_notes else ""
                    report.errors.append(
                        f"No supported coordinates for {finding.anchor_name}{details}"
                    )
                    continue
                resolution = self.store.resolve_place(candidate)
                place_id = resolution.place.place_id
                if place_id not in report.place_ids:
                    report.place_ids.append(place_id)
                if resolution.status.value == "matched":
                    report.matched_place_count += 1
                elif resolution.status.value == "created_uncertain":
                    report.uncertain_place_count += 1

            chunk = self.store.add_chunk(KnowledgeDraft(
                scope=finding.scope,
                anchor_name=finding.anchor_name,
                topic=finding.topic,
                content=finding.content,
                source_ids=source_ids,
                source_worker=self.provider_name,
                place_id=place_id,
                city=(place_city if finding.scope == Scope.PLACE else location.city)
                if finding.scope in {Scope.PLACE, Scope.STREET, Scope.DISTRICT, Scope.CITY} else "",
                region=(location.region if finding.scope != Scope.COUNTRY
                        and (finding.scope != Scope.PLACE or place_city == location.city) else ""),
                country=location.country,
            ))
            if chunk.chunk_id not in report.chunk_ids:
                report.chunk_ids.append(chunk.chunk_id)
            if chunk.chunk_id not in initial_chunk_ids:
                report.new_chunk_count += 1
                initial_chunk_ids.add(chunk.chunk_id)
            if report.first_chunk_latency_s is None:
                report.first_chunk_latency_s = time.perf_counter() - started
            if on_chunk is not None:
                try:
                    on_chunk(chunk)
                except Exception as exc:
                    report.errors.append(f"Chunk callback failed: {type(exc).__name__}: {exc}")

    def _valid_finding_lengths(self, finding: _Finding) -> bool:
        config = self.config
        return (
            len(finding.anchor_name) <= config.max_anchor_chars
            and len(finding.topic) <= config.max_topic_chars
            and config.min_chunk_chars <= len(finding.content) <= config.max_chunk_chars
            and len(finding.aliases) <= config.max_aliases
            and all(0 < len(alias) <= config.max_location_name_chars for alias in finding.aliases)
            and len(finding.street) <= config.max_location_name_chars
            and len(finding.city) <= config.max_location_name_chars
            and len(finding.address) <= config.max_address_chars
        )

    @staticmethod
    def _area_matches(scope: Scope, anchor: str, location: LocationContext) -> bool:
        valid = {
            Scope.STREET: (location.street,) if location.city else (),
            Scope.DISTRICT: (location.neighbourhood, location.district) if location.city else (),
            Scope.CITY: (location.city,),
            Scope.REGION: (location.region,),
            Scope.COUNTRY: (location.country,),
        }
        return bool(anchor and any(anchor == normalized_name(name) for name in valid.get(scope, ())))


class TavilyResearchWorker(WebResearchWorker):
    def __init__(
        self,
        client: WebResearchClient,
        model: ResearchLanguageModel,
        store: InMemoryKnowledgeStore,
        config: WebResearchConfig | None = None,
        *,
        place_locator: PlaceLocationResolver,
        tool_place_locator: ToolCallingPlaceLocator | None = None,
    ):
        super().__init__(
            provider_name="tavily", client=client, model=model, store=store,
            place_locator=place_locator, tool_place_locator=tool_place_locator,
            config=config
        )
