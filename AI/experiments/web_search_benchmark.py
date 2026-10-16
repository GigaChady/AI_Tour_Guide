"""Small, model-free web-search benchmark for the experiments notebook."""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests


TIMEOUT_SECONDS = 15
USER_AGENT = "AI-Tour-Guide-Search-Experiment/0.1 (research notebook)"


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str

    @property
    def domain(self) -> str:
        return urlsplit(self.url).netloc.lower()


@dataclass(frozen=True)
class SearchRun:
    method: str
    query: str
    seconds: float
    hits: list[SearchHit]
    error: str = ""

    @property
    def status(self) -> str:
        if self.error:
            return "error"
        return "ok" if self.hits else "empty"


def canonical_url(url: str) -> str:
    """Use a stable key for duplicate detection and manual relevance labels."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _clean_text(value: object) -> str:
    without_tags = re.sub(r"<[^>]*>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _hits(rows: Iterable[dict], max_results: int) -> list[SearchHit]:
    result: list[SearchHit] = []
    seen: set[str] = set()
    for row in rows:
        url = str(row.get("url") or "").strip()
        key = canonical_url(url)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(
            SearchHit(
                title=_clean_text(row.get("title")) or url,
                url=url,
                snippet=_clean_text(row.get("snippet"))[:1200],
            )
        )
        if len(result) >= max_results:
            break
    return result


def search_ddgs(query: str, max_results: int = 5, backend: str = "auto") -> list[SearchHit]:
    from ddgs import DDGS

    rows = DDGS(timeout=TIMEOUT_SECONDS).text(
        query, region="pl-pl", safesearch="moderate", max_results=max_results, backend=backend
    )
    return _hits(
        (
            {"title": row.get("title"), "url": row.get("href"), "snippet": row.get("body")}
            for row in rows
        ),
        max_results,
    )


def search_wikipedia_pl(query: str, max_results: int = 5) -> list[SearchHit]:
    response = requests.get(
        "https://pl.wikipedia.org/w/api.php",
        params={
            "action": "query", "list": "search", "srsearch": query,
            "srnamespace": 0, "srlimit": max_results, "format": "json", "utf8": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json().get("query", {}).get("search", [])
    return _hits(
        (
            {
                "title": row.get("title"),
                "url": f"https://pl.wikipedia.org/?curid={row['pageid']}",
                "snippet": row.get("snippet"),
            }
            for row in rows if row.get("pageid")
        ),
        max_results,
    )


def search_searxng(query: str, base_url: str, max_results: int = 5) -> list[SearchHit]:
    base = base_url.strip().rstrip("/")
    if urlsplit(base).scheme not in {"http", "https"} or not urlsplit(base).netloc:
        raise ValueError("SEARXNG_URL musi być adresem HTTP(S) instancji.")
    response = requests.get(
        f"{base}/search",
        params={"q": query, "format": "json", "language": "pl-PL", "safesearch": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return _hits(
        (
            {"title": row.get("title"), "url": row.get("url"), "snippet": row.get("content")}
            for row in response.json().get("results", [])
        ),
        max_results,
    )


def search_tavily(query: str, api_key: str, max_results: int = 5) -> list[SearchHit]:
    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "query": query, "search_depth": "basic", "max_results": max_results,
            "include_answer": False, "include_raw_content": False,
        },
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return _hits(
        (
            {"title": row.get("title"), "url": row.get("url"), "snippet": row.get("content")}
            for row in response.json().get("results", [])
        ),
        max_results,
    )


def search_exa(query: str, api_key: str, max_results: int = 5) -> list[SearchHit]:
    response = requests.post(
        "https://api.exa.ai/search",
        json={"query": query, "type": "auto", "numResults": max_results,
              "contents": {"highlights": True}},
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return _hits(
        (
            {"title": row.get("title"), "url": row.get("url"),
             "snippet": " ".join(row.get("highlights") or [])}
            for row in response.json().get("results", [])
        ),
        max_results,
    )


def search_brave(query: str, api_key: str, max_results: int = 5) -> list[SearchHit]:
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": max_results, "country": "PL", "search_lang": "pl",
                "safesearch": "moderate"},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return _hits(
        (
            {"title": row.get("title"), "url": row.get("url"),
             "snippet": row.get("description")}
            for row in response.json().get("web", {}).get("results", [])
        ),
        max_results,
    )


def run_queries(
    methods: dict[str, Callable[[str, int], list[SearchHit]]],
    queries: list[str],
    max_results: int = 5,
    pause_seconds: float = 0.5,
) -> list[SearchRun]:
    """Run each method on the same queries; report errors without aborting the comparison."""
    if not 1 <= max_results <= 10:
        raise ValueError("max_results musi być w przedziale 1–10")
    runs: list[SearchRun] = []
    for name, search in methods.items():
        for query in queries:
            started = time.perf_counter()
            try:
                hits = search(query, max_results)
                error = ""
            except Exception as exc:
                hits = []
                error = f"{type(exc).__name__}: {exc}"[:300]
            runs.append(SearchRun(name, query, round(time.perf_counter() - started, 3), hits, error))
            if pause_seconds > 0:
                time.sleep(pause_seconds)
    return runs


def summarize(runs: list[SearchRun]) -> list[dict]:
    summary: dict[str, dict] = {}
    for run in runs:
        row = summary.setdefault(run.method, {
            "method": run.method, "queries": 0, "ok": 0, "empty": 0,
            "errors": 0, "results": 0, "domains": set(), "snippets": 0, "seconds": 0.0,
        })
        row["queries"] += 1
        row[run.status if run.status != "error" else "errors"] += 1
        row["results"] += len(run.hits)
        row["domains"].update(hit.domain for hit in run.hits)
        row["snippets"] += sum(bool(hit.snippet) for hit in run.hits)
        row["seconds"] += run.seconds
    return [
        {
            **{key: value for key, value in row.items() if key not in {"domains", "seconds"}},
            "unique_domains": len(row["domains"]),
            "mean_seconds": round(row["seconds"] / row["queries"], 2),
        }
        for row in summary.values()
    ]
