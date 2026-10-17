from __future__ import annotations

from typing import Any

import requests

from integrations.llm.nvidia.config import NvidiaConfig


class NvidiaToolCallingModel:
    """Small Chat Completions adapter for the geocoding tool loop."""

    def __init__(
        self, config: NvidiaConfig | None = None, *, api_key: str,
        session: requests.Session | None = None,
        chat_template_kwargs: dict[str, Any] | None = None,
    ):
        if not api_key.strip():
            raise ValueError("NVIDIA API key is required for tool calling")
        self.config = config or NvidiaConfig()
        self.api_key = api_key.strip()
        self.session = session or requests.Session()
        self.chat_template_kwargs = (dict(chat_template_kwargs)
                                     if chat_template_kwargs is not None else None)

    def create(
        self, messages: list[dict[str, Any]], *,
        tools: list[dict[str, Any]], tool_choice: str = "auto",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        if self.chat_template_kwargs is not None:
            payload["chat_template_kwargs"] = self.chat_template_kwargs
        elif self.config.reasoning_effort:
            payload["reasoning_effort"] = self.config.reasoning_effort
        response = self.session.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            json=payload, timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices") or []
        if not choices or not isinstance(choices[0].get("message"), dict):
            raise RuntimeError("NVIDIA returned no assistant message for geocoding")
        return choices[0]["message"]
