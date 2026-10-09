from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import requests

from integrations.knowledge.wikimedia.config import WikimediaConfig
from narration.schemas import LocationAddress, SelectedPoi


logger = logging.getLogger(__name__)


class WikimediaSearchClient:
    source_type = "wikimedia"

    def __init__(
        self,
        config: WikimediaConfig | None = None,
        user_agent: str | None = None,
        timeout: int | None = None,
        languages: tuple[str, ...] | None = None,
        max_extract_chars: int | None = None,
        session: requests.Session | None = None,
    ):
        config = config or WikimediaConfig()
        self.user_agent = user_agent or config.user_agent
        self.timeout = timeout if timeout is not None else config.timeout_seconds
        self.languages = languages or config.languages
        self.max_extract_chars = (
            max_extract_chars
            if max_extract_chars is not None
            else config.max_extract_chars
        )
        self.session = session or requests.Session()

    def search_poi(self, selected_poi: SelectedPoi, address: LocationAddress) -> str:
        poi = selected_poi.poi

        if poi.wikipedia:
            summary = self._summary_from_wikipedia_tag(poi.wikipedia)
            if summary:
                return summary

        if poi.wikidata:
            summary = self._summary_from_wikidata_id(poi.wikidata)
            if summary:
                return summary

        return self.search(self._build_search_query(selected_poi, address))

    def search(self, query: str) -> str:
        logger.info('Starting Wikimedia query "%s"', query)

        for language in self.languages:
            title = self._find_page_title(language=language, query=query)
            if not title:
                continue

            context = self._fetch_page_context(language=language, title=title)
            if context:
                logger.info('Finished Wikimedia query "%s" using %s:%s', query, language, title)
                return context

        logger.info('No Wikimedia result for query "%s"', query)
        return ""

    def _summary_from_wikipedia_tag(self, wikipedia_tag: str) -> str:
        language, title = self._parse_wikipedia_tag(wikipedia_tag)
        if not language or not title:
            return ""
        return self._fetch_page_context(language=language, title=title)

    def _summary_from_wikidata_id(self, wikidata_id: str) -> str:
        entity = self._fetch_wikidata_entity(wikidata_id)
        if not entity:
            return ""

        for language in self.languages:
            title = (
                entity.get("sitelinks", {})
                .get(f"{language}wiki", {})
                .get("title")
            )
            if title:
                context = self._fetch_page_context(language=language, title=title)
                if context:
                    return context

        descriptions = entity.get("descriptions", {})
        labels = entity.get("labels", {})
        context_parts = []
        for language in self.languages:
            label = labels.get(language, {}).get("value")
            description = descriptions.get(language, {}).get("value")
            if label or description:
                context_parts.append(
                    " - ".join(part for part in (label, description) if part)
                )

        return "\n".join(dict.fromkeys(context_parts))

    def _fetch_wikidata_entity(self, wikidata_id: str) -> dict[str, Any] | None:
        try:
            response = self.session.get(
                f"https://www.wikidata.org/wiki/Special:EntityData/{quote(wikidata_id)}.json",
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("entities", {}).get(wikidata_id)
        except Exception as e:
            logger.warning("Wikidata lookup failed for %s: %s", wikidata_id, e)
            return None

    def _find_page_title(self, language: str, query: str) -> str | None:
        try:
            response = self.session.get(
                f"https://{language}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": 1,
                    "format": "json",
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            results = response.json().get("query", {}).get("search", [])
            if not results:
                return None
            return results[0].get("title")
        except Exception as e:
            logger.warning("Wikipedia search failed for %s query '%s': %s", language, query, e)
            return None

    def _fetch_page_context(self, language: str, title: str) -> str:
        extract = self._fetch_page_extract(language=language, title=title)
        if extract:
            return extract
        return self._fetch_page_summary(language=language, title=title)

    def _fetch_page_extract(self, language: str, title: str) -> str:
        try:
            response = self.session.get(
                f"https://{language}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "prop": "extracts",
                    "titles": title,
                    "explaintext": True,
                    "redirects": True,
                    "format": "json",
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning("Wikipedia extract failed for %s:%s: %s", language, title, e)
            return ""

        pages = data.get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        extract = (page.get("extract") or "").strip()
        if not extract:
            return ""

        page_title = page.get("title") or title
        extract = self._truncate_extract(extract)
        return f"Wikipedia ({language}) title: {page_title}\nExtract: {extract}"

    def _fetch_page_summary(self, language: str, title: str) -> str:
        try:
            response = self.session.get(
                f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning("Wikipedia summary failed for %s:%s: %s", language, title, e)
            return ""

        title = data.get("title") or title
        extract = data.get("extract") or ""
        if not extract:
            return ""

        return f"Wikipedia ({language}) title: {title}\nSummary: {extract}"

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent}

    def _truncate_extract(self, extract: str) -> str:
        if len(extract) <= self.max_extract_chars:
            return extract

        truncated = extract[: self.max_extract_chars].rstrip()
        last_sentence_end = max(
            truncated.rfind("."),
            truncated.rfind("!"),
            truncated.rfind("?"),
        )
        if last_sentence_end >= self.max_extract_chars * 0.6:
            return truncated[: last_sentence_end + 1]
        return truncated

    @staticmethod
    def _parse_wikipedia_tag(wikipedia_tag: str) -> tuple[str | None, str | None]:
        if ":" not in wikipedia_tag:
            return None, None
        language, title = wikipedia_tag.split(":", 1)
        language = language.strip()
        title = title.strip().replace(" ", "_")
        if not language or not title:
            return None, None
        return language, title

    @staticmethod
    def _build_search_query(selected_poi: SelectedPoi, address: LocationAddress) -> str:
        parts = [selected_poi.poi.name, address.general_location]
        return " ".join(part for part in parts if part)
