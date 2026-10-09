from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

import requests


@dataclass
class NvidiaResponse:
    message: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class NvidiaChatCompletionsClient:
    """Minimal client for NVIDIA's OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        endpoint: str = "https://integrate.api.nvidia.com/v1/chat/completions",
        max_tokens: int = 65_536,
        reasoning_budget: int = 16_384,
        temperature: float = 0.6,
        top_p: float = 0.95,
        timeout_seconds: int = 180,
        max_retries: int = 4,
        retry_backoff_seconds: float = 2.0,
    ):
        clean_key = api_key.strip()
        if not clean_key or clean_key.startswith("WKLEJ_"):
            raise ValueError("Paste a valid NVIDIA API key")
        if reasoning_budget >= max_tokens:
            raise ValueError("reasoning_budget must be smaller than max_tokens")
        self.api_key = clean_key
        self.model = model
        self.endpoint = endpoint
        self.max_tokens = max_tokens
        self.reasoning_budget = reasoning_budget
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def create(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> NvidiaResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "messages": messages,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "reasoning_budget": self.reasoning_budget,
            "stream": False,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        response = None
        retryable_statuses = {429, 500, 502, 503, 504}
        for attempt in range(self.max_retries + 1):
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            if response.status_code not in retryable_statuses or attempt >= self.max_retries:
                break
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 0.0
            except ValueError:
                delay = 0.0
            delay = max(delay, self.retry_backoff_seconds * (2**attempt))
            time.sleep(min(delay, 30.0))

        assert response is not None
        if not response.ok:
            body = response.text[:4_000]
            raise RuntimeError(
                f"NVIDIA API returned HTTP {response.status_code}: {body}"
            )
        data = response.json()
        choices = data.get("choices") or []
        if not choices or not isinstance(choices[0].get("message"), dict):
            raise RuntimeError(f"Unexpected NVIDIA response: {data}")
        return NvidiaResponse(
            message=choices[0]["message"],
            usage=data.get("usage") or {},
            raw=data,
        )
