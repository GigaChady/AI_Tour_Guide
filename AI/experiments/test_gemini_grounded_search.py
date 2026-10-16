from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from experiments.gemini_grounded_search import GeminiGroundedResearch
from experiments.tool_calling.geo_provider import MockGeoProvider
from experiments.tool_calling.knowledge_store import InMemoryKnowledgeStore


class GeminiGroundedResearchTest(unittest.TestCase):
    @patch("experiments.gemini_grounded_search.requests.post")
    def test_stores_only_segments_with_grounding_sources(self, post: Mock) -> None:
        response = Mock(ok=True)
        response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Nadodrze ma historyczną zabudowę kamienicową."}
                        ]
                    },
                    "groundingMetadata": {
                        "webSearchQueries": ["Nadodrze historia"],
                        "groundingChunks": [
                            {
                                "web": {
                                    "uri": "https://example.org/nadodrze",
                                    "title": "Historia Nadodrza",
                                }
                            }
                        ],
                        "groundingSupports": [
                            {
                                "segment": {
                                    "text": "Nadodrze ma historyczną zabudowę kamienicową."
                                },
                                "groundingChunkIndices": [0],
                            },
                            {
                                "segment": {"text": "Niepotwierdzony fakt o okolicy."},
                                "groundingChunkIndices": [],
                            },
                        ],
                    },
                }
            ],
            "usageMetadata": {"totalTokenCount": 123},
        }
        post.return_value = response
        store = InMemoryKnowledgeStore()
        research = GeminiGroundedResearch("test-key", MockGeoProvider(), store)

        run = research.run(51.1216, 17.0352)

        self.assertTrue(run.store_result.success)
        self.assertEqual(len(store.chunks), 1)
        self.assertEqual(len(store.sources), 1)
        self.assertEqual(next(iter(store.chunks.values())).source_ids, ["src_001"])
        self.assertEqual(run.search_queries, ["Nadodrze historia"])
        self.assertEqual(run.usage["totalTokenCount"], 123)
        request = post.call_args
        self.assertIn("gemini-2.5-flash:generateContent", request.args[0])
        self.assertEqual(request.kwargs["json"]["tools"], [{"google_search": {}}])

    @patch("experiments.gemini_grounded_search.requests.post")
    def test_does_not_store_ungrounded_answer(self, post: Mock) -> None:
        response = Mock(ok=True)
        response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "Twierdzenie bez źródeł."}]}}
            ]
        }
        post.return_value = response
        store = InMemoryKnowledgeStore()

        run = GeminiGroundedResearch("test-key", MockGeoProvider(), store).run(
            51.1216, 17.0352
        )

        self.assertFalse(run.store_result.success)
        self.assertFalse(store.chunks)
        self.assertIn("Brak fragmentów", run.store_result.validation_errors[0])


if __name__ == "__main__":
    unittest.main()
