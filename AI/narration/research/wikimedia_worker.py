from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable

from narration.knowledge import (
    InMemoryKnowledgeStore,
    KnowledgeChunk,
    KnowledgeDraft,
    LocationContext,
    Scope,
    Source,
)
from narration.knowledge.normalization import normalized_name
from narration.research.contracts import (
    ResearchBudgetExhausted,
    WikimediaArticle,
    WikimediaArticleClient,
)

_HEADING = re.compile(r"(?m)^={2,6}\s*([^=\n]+?)\s*={2,6}\s*$")
_SKIP_TOPICS = {
    "bibliografia", "bibliography", "przypisy", "references", "notes",
    "linki zewnetrzne", "external links", "zobacz tez", "see also",
}
_TOPIC_KEYWORDS = (
    ("history", ("historia", "history", "geschichte")),
    ("architecture", ("architektura", "architecture", "baukunst")),
    ("culture", ("kultura", "culture", "kultur")),
    ("geography", ("geografia", "geography", "geografie")),
)


@dataclass(frozen=True)
class WikimediaWorkerConfig:
    max_scope_lookups: int = 5
    max_articles: int = 3
    max_total_chunks: int = 8
    max_chunks_per_article: int = 3
    max_chunk_chars: int = 900
    fetch_sections_for_first_n_articles: int = 2

    def __post_init__(self):
        if any(value <= 0 for value in (
            self.max_scope_lookups, self.max_articles, self.max_total_chunks,
            self.max_chunks_per_article, self.max_chunk_chars,
        )) or self.fetch_sections_for_first_n_articles < 0:
            raise ValueError("Invalid Wikimedia worker limits")


@dataclass(frozen=True)
class WikimediaAttempt:
    scope: Scope
    anchor_name: str
    status: str
    article_title: str = ""
    error: str = ""


@dataclass
class WikimediaRun:
    attempts: list[WikimediaAttempt] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    article_count: int = 0
    api_request_count: int = 0
    latency_s: float = 0.0
    first_chunk_latency_s: float | None = None


def _short_fragment(text: str, max_chars: int) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    prefix = clean[:max_chars]
    last_sentence = max(prefix.rfind("."), prefix.rfind("!"), prefix.rfind("?"))
    if last_sentence >= max_chars * 0.6:
        return prefix[: last_sentence + 1]
    last_space = prefix.rfind(" ")
    return prefix[:last_space] if last_space >= max_chars * 0.6 else prefix


def _section_fragments(extract: str, max_chars: int) -> list[tuple[str, str]]:
    headings = list(_HEADING.finditer(extract))
    sections: list[tuple[int, int, str, str]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(extract)
        title = normalized_name(heading.group(1))
        if title in _SKIP_TOPICS:
            continue
        body = _short_fragment(extract[heading.end():end], max_chars)
        if len(body) < 40:
            continue
        topic = next(
            (key for key, aliases in _TOPIC_KEYWORDS if any(word in title for word in aliases)),
            title.replace(" ", "_")[:60],
        )
        priority = next(
            (position for position, (_, aliases) in enumerate(_TOPIC_KEYWORDS)
             if any(word in title for word in aliases)),
            len(_TOPIC_KEYWORDS),
        )
        sections.append((priority, index, topic, body))
    sections.sort(key=lambda row: (row[0], row[1]))
    return [(topic, body) for _, _, topic, body in sections]


class WikimediaWorker:
    def __init__(
        self,
        article_client: WikimediaArticleClient,
        store: InMemoryKnowledgeStore,
        config: WikimediaWorkerConfig | None = None,
    ):
        self.article_client = article_client
        self.store = store
        self.config = config or WikimediaWorkerConfig()

    def run(
        self,
        location: LocationContext,
        *,
        on_chunk: Callable[[KnowledgeChunk], None] | None = None,
    ) -> WikimediaRun:
        started = time.perf_counter()
        requests_before = self.article_client.request_count
        report = WikimediaRun()
        seen_anchors: set[tuple[Scope, str]] = set()

        scopes = (
            (Scope.DISTRICT, location.neighbourhood, location.city),
            (Scope.DISTRICT, location.district, location.city),
            (Scope.CITY, location.city, location.country),
            (Scope.REGION, location.region, location.country),
            (Scope.COUNTRY, location.country, ""),
        )
        for scope, anchor, disambiguator in scopes:
            if len(report.chunk_ids) >= self.config.max_total_chunks:
                break
            if not anchor or (scope == Scope.DISTRICT and not location.city):
                continue
            identity = (scope, normalized_name(anchor))
            if identity in seen_anchors:
                continue
            seen_anchors.add(identity)
            if len(report.attempts) >= self.config.max_scope_lookups:
                break
            if report.article_count >= self.config.max_articles:
                break

            try:
                article = self.article_client.find_article(
                    anchor, disambiguator=disambiguator
                )
            except ResearchBudgetExhausted as exc:
                report.attempts.append(WikimediaAttempt(scope, anchor, "budget_exhausted", error=str(exc)))
                break
            except Exception as exc:
                report.attempts.append(WikimediaAttempt(scope, anchor, "error", error=str(exc)))
                continue
            if article is None:
                report.attempts.append(WikimediaAttempt(scope, anchor, "not_found"))
                continue

            report.article_count += 1
            report.attempts.append(
                WikimediaAttempt(scope, anchor, "found", article_title=article.title)
            )
            lead = _short_fragment(article.lead, self.config.max_chunk_chars)
            if not lead:
                continue
            source = self.store.add_source(Source.from_url(
                provider="wikimedia", title=article.title, url=article.url,
                evidence_text=lead,
            ))
            self._save_chunk(report, started, location, scope, anchor, "overview", lead,
                             source.source_id, on_chunk)

            if (
                report.article_count > self.config.fetch_sections_for_first_n_articles
                or len(report.chunk_ids) >= self.config.max_total_chunks
                or self.config.max_chunks_per_article <= 1
            ):
                continue
            try:
                full_extract = self.article_client.fetch_sections(article)
            except ResearchBudgetExhausted as exc:
                report.attempts.append(WikimediaAttempt(scope, anchor, "budget_exhausted", error=str(exc)))
                break
            except Exception as exc:
                report.attempts.append(WikimediaAttempt(scope, anchor, "sections_error", error=str(exc)))
                continue

            sections = _section_fragments(full_extract, self.config.max_chunk_chars)
            selected = sections[: self.config.max_chunks_per_article - 1]
            if selected:
                self.store.add_source(Source.from_url(
                    provider="wikimedia", title=article.title, url=article.url,
                    evidence_text="\n".join([lead, *(body for _, body in selected)]),
                ))
            for topic, body in selected:
                if len(report.chunk_ids) >= self.config.max_total_chunks:
                    break
                self._save_chunk(report, started, location, scope, anchor, topic, body,
                                 source.source_id, on_chunk)

        report.api_request_count = self.article_client.request_count - requests_before
        report.latency_s = time.perf_counter() - started
        return report

    def _save_chunk(
        self,
        report: WikimediaRun,
        started: float,
        location: LocationContext,
        scope: Scope,
        anchor: str,
        topic: str,
        content: str,
        source_id: str,
        on_chunk: Callable[[KnowledgeChunk], None] | None,
    ) -> None:
        city = location.city if scope in {Scope.DISTRICT, Scope.CITY} else ""
        region = location.region if scope != Scope.COUNTRY else ""
        chunk = self.store.add_chunk(KnowledgeDraft(
            scope=scope, anchor_name=anchor, topic=topic, content=content,
            source_ids=[source_id], source_worker="wikimedia",
            city=city, region=region, country=location.country,
        ))
        if chunk.chunk_id not in report.chunk_ids:
            report.chunk_ids.append(chunk.chunk_id)
        if report.first_chunk_latency_s is None:
            report.first_chunk_latency_s = time.perf_counter() - started
        if on_chunk is not None:
            on_chunk(chunk)
