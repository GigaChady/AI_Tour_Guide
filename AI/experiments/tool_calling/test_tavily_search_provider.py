from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from experiments.tool_calling.tavily_search_provider import TavilyWebSearchProvider


def _response(payload: dict) -> Mock:
    response = Mock()
    response.json.return_value = payload
    return response


class TavilyWebSearchProviderTest(unittest.TestCase):
    @patch("experiments.tool_calling.tavily_search_provider.requests.post")
    def test_keyless_search_and_extract_preserve_source_contract(self, post: Mock) -> None:
        url = "https://example.org/nadodrze"
        post.side_effect = [
            _response(
                {
                    "results": [
                        {"title": "Nadodrze", "url": url, "content": "Krótki opis"}
                    ]
                }
            ),
            _response({"results": [{"url": url, "raw_content": "A" * 600}]}),
        ]
        provider = TavilyWebSearchProvider(search_depth="basic")

        results = provider.search("  Nadodrze Wrocław  ")
        self.assertEqual(results[0].source_id, "src_001")
        self.assertEqual(results[0].snippet, "Krótki opis")
        self.assertEqual(provider.read_source_ids, set())
        page = provider.read_result("src_001", max_chars=500)

        self.assertEqual(len(page["content"]), 500)
        self.assertTrue(page["truncated"])
        self.assertEqual(provider.read_source_ids, {"src_001"})
        self.assertEqual(provider.get_source("src_001").url, url)
        self.assertEqual(provider.query_log, ["Nadodrze Wrocław"])
        search_call, extract_call = post.call_args_list
        self.assertEqual(search_call.args[0], "https://api.tavily.com/search")
        self.assertEqual(search_call.kwargs["json"]["search_depth"], "basic")
        self.assertEqual(
            search_call.kwargs["headers"]["X-Tavily-Access-Mode"], "keyless"
        )
        self.assertEqual(extract_call.args[0], "https://api.tavily.com/extract")
        self.assertEqual(extract_call.kwargs["json"]["urls"], [url])

    @patch("experiments.tool_calling.tavily_search_provider.requests.post")
    def test_failed_extract_does_not_authorize_source(self, post: Mock) -> None:
        url = "https://example.org/nadodrze"
        post.side_effect = [
            _response({"results": [{"url": url, "content": "Opis"}]}),
            _response(
                {
                    "results": [],
                    "failed_results": [{"url": url, "error": "Page unavailable"}],
                }
            ),
        ]
        provider = TavilyWebSearchProvider(api_key="tvly-test")
        provider.search("Nadodrze")

        with self.assertRaisesRegex(RuntimeError, "Page unavailable"):
            provider.read_result("src_001")

        self.assertEqual(provider.read_source_ids, set())
        self.assertEqual(
            post.call_args_list[0].kwargs["headers"]["Authorization"],
            "Bearer tvly-test",
        )


if __name__ == "__main__":
    unittest.main()
