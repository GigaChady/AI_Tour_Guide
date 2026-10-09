from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from experiments.tool_calling.agent import NvidiaToolCallingResearchAgent
from experiments.tool_calling.geo_provider import MockGeoProvider
from experiments.tool_calling.knowledge_store import InMemoryKnowledgeStore
from experiments.tool_calling.nvidia_client import (
    NvidiaChatCompletionsClient,
    NvidiaResponse,
)
from experiments.tool_calling.toolbox import ResearchToolbox
from experiments.tool_calling.web_search_provider import MockWebSearchProvider


def _tool_call(call_id: str, name: str, arguments: dict) -> NvidiaResponse:
    return NvidiaResponse(
        message={
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments),
                    },
                }
            ],
        },
        usage={"total_tokens": 10},
    )


class _ScriptedClient:
    def __init__(self, responses: list[NvidiaResponse]):
        self.responses = iter(responses)
        self.requests: list[dict] = []

    def create(self, messages, *, tools=None, tool_choice="auto"):
        self.requests.append(
            {"messages": list(messages), "tools": tools, "tool_choice": tool_choice}
        )
        return next(self.responses)


class NvidiaClientTest(unittest.TestCase):
    @patch("experiments.tool_calling.nvidia_client.requests.post")
    def test_uses_nvidia_chat_completions_payload(self, post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"total_tokens": 3},
        }
        post.return_value = response
        client = NvidiaChatCompletionsClient("nvapi-test", max_retries=0)

        result = client.create(
            [{"role": "user", "content": "test"}],
            tools=[{"type": "function", "function": {"name": "test"}}],
        )

        request = post.call_args.kwargs
        self.assertEqual(request["headers"]["Authorization"], "Bearer nvapi-test")
        self.assertEqual(request["json"]["reasoning_budget"], 16_384)
        self.assertEqual(request["json"]["tool_choice"], "auto")
        self.assertEqual(result.message["content"], "ok")


class AgentLoopTest(unittest.TestCase):
    def test_executes_openai_compatible_tool_loop(self) -> None:
        chunk = {
            "anchor_type": "AREA",
            "anchor_name": "Nadodrze",
            "canonical_name": "Nadodrze",
            "topic": "urban_history",
            "content": "Nadodrze zachowało historyczne kwartały zabudowy.",
            "source_ids": ["src_001"],
            "confidence": 0.8,
        }
        client = _ScriptedClient(
            [
                _tool_call("call_1", "reverse_geocode", {"lat": 51.1216, "lon": 17.0352}),
                _tool_call("call_2", "get_area_coverage", {}),
                _tool_call("call_3", "web_search", {"query": "Nadodrze historia"}),
                _tool_call("call_4", "read_search_result", {"source_id": "src_001"}),
                _tool_call("call_5", "store_research", {"places": [], "chunks": [chunk]}),
            ]
        )
        toolbox = ResearchToolbox(
            MockWebSearchProvider(),
            MockGeoProvider(),
            InMemoryKnowledgeStore(),
        )

        run = NvidiaToolCallingResearchAgent(client, toolbox).run(51.1216, 17.0352)

        self.assertTrue(run.store_result.success)
        self.assertEqual([entry.tool_name for entry in run.trace][-1], "store_research")
        self.assertEqual(run.usage["total_tokens"], 50)
        followup_messages = client.requests[-1]["messages"]
        self.assertTrue(any(message["role"] == "tool" for message in followup_messages))


if __name__ == "__main__":
    unittest.main()
