from __future__ import annotations

import unittest
import sys
import types
from unittest.mock import Mock, patch

from experiments.web_search_benchmark import (
    SearchHit,
    canonical_url,
    run_queries,
    search_brave,
    search_ddgs,
    search_exa,
    search_searxng,
    search_tavily,
    search_wikipedia_pl,
    summarize,
)


def json_response(payload: dict) -> Mock:
    response = Mock()
    response.json.return_value = payload
    return response


class WebSearchBenchmarkTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_parameters_and_fragments(self):
        self.assertEqual(
            canonical_url("https://Example.org/page/?utm_source=x&id=2#section"),
            "https://example.org/page?id=2",
        )
        self.assertEqual(canonical_url("file:///tmp/test"), "")

    def test_ddgs_backend_and_deduplication(self):
        client = Mock()
        client.text.return_value = [
            {"title": "Pierwszy", "href": "https://example.org/a?utm_source=x", "body": "A"},
            {"title": "Duplikat", "href": "https://example.org/a", "body": "B"},
        ]
        fake_ddgs = types.ModuleType("ddgs")
        fake_ddgs.DDGS = Mock(return_value=client)

        with patch.dict(sys.modules, {"ddgs": fake_ddgs}):
            hits = search_ddgs("Nadodrze", backend="google")

        self.assertEqual(len(hits), 1)
        self.assertEqual(client.text.call_args.kwargs["backend"], "google")
        self.assertEqual(client.text.call_args.kwargs["region"], "pl-pl")

    @patch("experiments.web_search_benchmark.requests.get")
    def test_searxng_reads_json_results(self, get: Mock):
        get.return_value = json_response({"results": [
            {"title": "S", "url": "https://example.org/s", "content": "Opis"}
        ]})

        hits = search_searxng("Nadodrze", "https://search.example.org")

        self.assertEqual(hits[0].snippet, "Opis")
        self.assertEqual(get.call_args.args[0], "https://search.example.org/search")
        self.assertEqual(get.call_args.kwargs["params"]["format"], "json")

    @patch("experiments.web_search_benchmark.requests.get")
    def test_wikipedia_result_has_article_url_and_plain_snippet(self, get: Mock):
        get.return_value = json_response({"query": {"search": [
            {"pageid": 123, "title": "Nadodrze", "snippet": "<span>Wrocław</span> &amp; okolice"}
        ]}})

        hits = search_wikipedia_pl("Nadodrze", 5)

        self.assertEqual(hits[0].url, "https://pl.wikipedia.org/?curid=123")
        self.assertEqual(hits[0].snippet, "Wrocław & okolice")
        self.assertEqual(get.call_args.kwargs["params"]["srsearch"], "Nadodrze")

    @patch("experiments.web_search_benchmark.requests.post")
    def test_tavily_and_exa_normalize_snippets(self, post: Mock):
        post.side_effect = [
            json_response({"results": [{"title": "T", "url": "https://example.org/t", "content": "Tavily"}]}),
            json_response({"results": [{"title": "E", "url": "https://example.org/e", "highlights": ["A", "B"]}]}),
        ]

        self.assertEqual(search_tavily("test", "secret")[0].snippet, "Tavily")
        self.assertEqual(search_exa("test", "secret")[0].snippet, "A B")
        self.assertEqual(post.call_args_list[0].kwargs["json"]["search_depth"], "basic")
        self.assertEqual(post.call_args_list[1].kwargs["json"]["contents"], {"highlights": True})

    @patch("experiments.web_search_benchmark.requests.get")
    def test_brave_reads_web_results_and_sends_polish_locale(self, get: Mock):
        get.return_value = json_response({"web": {"results": [
            {"title": "Brave", "url": "https://example.org/b", "description": "Opis"}
        ]}})

        hits = search_brave("test", "secret")

        self.assertEqual(hits[0].snippet, "Opis")
        self.assertEqual(get.call_args.kwargs["params"]["country"], "PL")
        self.assertEqual(get.call_args.kwargs["params"]["search_lang"], "pl")

    def test_failed_provider_does_not_abort_other_queries(self):
        def broken(query: str, max_results: int) -> list[SearchHit]:
            raise RuntimeError("blocked")

        methods = {
            "broken": broken,
            "working": lambda query, max_results: [SearchHit("Title", "https://example.org", "Snippet")],
        }
        runs = run_queries(methods, ["first", "second"], pause_seconds=0)

        self.assertEqual([run.status for run in runs], ["error", "error", "ok", "ok"])
        self.assertEqual(summarize(runs)[1]["unique_domains"], 1)


if __name__ == "__main__":
    unittest.main()
