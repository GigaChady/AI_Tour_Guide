from __future__ import annotations

import re
from urllib.parse import quote

import requests

from narration.knowledge import GeocodedPlace
from narration.knowledge.normalization import normalized_name
from narration.research.contracts import ResearchBudgetExhausted, WikimediaArticle


class WikimediaArticleProvider:
    """Structured Wikipedia article access for the fast research worker."""

    def __init__(
        self,
        *,
        user_agent: str,
        languages: tuple[str, ...] = ("pl", "en"),
        timeout_seconds: int = 8,
        max_requests: int = 12,
        max_full_extract_chars: int = 12_000,
        session: requests.Session | None = None,
    ):
        if not user_agent.strip() or "unavailable" in user_agent.casefold():
            raise ValueError("Set a descriptive WIKIMEDIA_USER_AGENT before live research")
        if not languages or any(not re.fullmatch(r"[a-z-]{2,12}", lang) for lang in languages):
            raise ValueError("Invalid Wikipedia language list")
        if timeout_seconds <= 0 or max_requests <= 0 or max_full_extract_chars <= 0:
            raise ValueError("Provider limits must be positive")
        self.user_agent = user_agent
        self.languages = languages
        self.timeout_seconds = timeout_seconds
        self.max_requests = max_requests
        self.max_full_extract_chars = max_full_extract_chars
        self.session = session or requests.Session()
        self.request_count = 0

    def find_article(
        self, name: str, *, disambiguator: str = ""
    ) -> WikimediaArticle | None:
        for language in self.languages:
            page = self._page(language, name, intro=True)
            article = self._article_from_page(language, name, disambiguator, page)
            if article is not None:
                return article

            for title in self._search_titles(language, name, disambiguator):
                if not self._title_matches(title, name, disambiguator):
                    continue
                page = self._page(language, title, intro=True)
                article = self._article_from_page(language, name, disambiguator, page)
                if article is not None:
                    return article
        return None

    def fetch_sections(self, article: WikimediaArticle) -> str:
        page = self._page(article.language, article.title, intro=False)
        if page is None or "disambiguation" in (page.get("pageprops") or {}):
            return ""
        return str(page.get("extract") or "")[: self.max_full_extract_chars]

    def find_place_coordinates(
        self, name: str, *, disambiguator: str = ""
    ) -> GeocodedPlace | None:
        article = self.find_article(name, disambiguator=disambiguator)
        if article is None or article.lat is None or article.lon is None:
            return None
        if disambiguator:
            context_words = normalized_name(f"{article.title} {article.lead}").split()
            city_words = normalized_name(disambiguator).split()
            if not all(
                any(word.startswith(city_word[:max(3, len(city_word) - 2)])
                    for word in context_words)
                for city_word in city_words
            ):
                return None
        external_ids = {"wikipedia_page": f"{article.language}:{article.page_id}"} if article.page_id else {}
        if article.wikidata_id:
            external_ids["wikidata"] = article.wikidata_id
        return GeocodedPlace(
            name=article.title, lat=article.lat, lon=article.lon,
            coordinate_source=f"wikipedia:{article.language}:{article.page_id or article.title}",
            city=disambiguator, external_ids=external_ids,
        )

    def _page(self, language: str, title: str, *, intro: bool) -> dict | None:
        params = {
            "action": "query",
            "prop": "extracts|pageprops|coordinates" if intro else "extracts",
            "titles": title,
            "explaintext": 1,
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        }
        if intro:
            params.update({"exintro": 1, "exchars": 1200,
                           "ppprop": "disambiguation|wikibase_item", "coprimary": "primary"})
        else:
            params["exsectionformat"] = "wiki"
        data = self._get(language, params)
        pages = data.get("query", {}).get("pages") or []
        if not pages:
            return None
        page = pages[0]
        return None if page.get("missing") or page.get("invalid") else page

    def _search_titles(self, language: str, name: str, disambiguator: str) -> list[str]:
        query = " ".join(part for part in (name, disambiguator) if part)
        data = self._get(
            language,
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 3,
                "srnamespace": 0,
                "format": "json",
            },
        )
        return [str(row.get("title") or "") for row in data.get("query", {}).get("search") or []]

    def _get(self, language: str, params: dict) -> dict:
        if self.request_count >= self.max_requests:
            raise ResearchBudgetExhausted("Wikimedia API request budget exhausted")
        self.request_count += 1
        response = self.session.get(
            f"https://{language}.wikipedia.org/w/api.php",
            params=params,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "error" in payload:
            raise RuntimeError(f"Invalid Wikimedia API response: {payload.get('error') if isinstance(payload, dict) else 'not an object'}")
        return payload

    @staticmethod
    def _title_matches(title: str, name: str, disambiguator: str) -> bool:
        title_key = normalized_name(title)
        name_key = normalized_name(name)
        if title_key == name_key:
            return True
        context_key = normalized_name(disambiguator)
        return bool(context_key and title_key.startswith(name_key + " ") and context_key in title_key)

    def _article_from_page(
        self, language: str, name: str, disambiguator: str, page: dict | None
    ) -> WikimediaArticle | None:
        if page is None or "disambiguation" in (page.get("pageprops") or {}):
            return None
        title = str(page.get("title") or "")
        lead = str(page.get("extract") or "").strip()
        if not lead or not self._title_matches(title, name, disambiguator):
            return None
        url = f"https://{language}.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='()')}"
        point = next((row for row in page.get("coordinates") or []
                      if row.get("globe", "earth") == "earth"), None)
        try:
            lat = float(point["lat"]) if point else None
            lon = float(point["lon"]) if point else None
        except (TypeError, ValueError, KeyError):
            lat = lon = None
        return WikimediaArticle(
            title=title, language=language, url=url, lead=lead,
            page_id=page.get("pageid"),
            wikidata_id=str((page.get("pageprops") or {}).get("wikibase_item") or ""),
            lat=lat, lon=lon,
        )
