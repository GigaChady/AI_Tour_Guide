from __future__ import annotations

from integrations.llm.nvidia.config import NvidiaConfig
from shared.retry import call_with_timeout_retry


class NvidiaLanguageModel:
    def __init__(self, config: NvidiaConfig | None = None, api_key: str | None = None):
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        self.config = config or NvidiaConfig()
        options = {"nvidia_api_key": api_key} if api_key else {}
        if self.config.reasoning_effort:
            options["model_kwargs"] = {"reasoning_effort": self.config.reasoning_effort}
        self.model = ChatNVIDIA(
            model=self.config.model_name,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_tokens=self.config.max_tokens,
            timeout=self.config.request_timeout_seconds,
            **options,
        )

    def generate(self, messages: list[tuple[str, str]]) -> str:
        response = call_with_timeout_retry(
            # These are complete messages, not templates. Source text and JSON
            # examples may contain braces that LangChain would parse as fields.
            lambda: self.model.invoke(messages),
            timeout_seconds=self.config.request_timeout_seconds,
            max_retries=self.config.max_retries,
            backoff_seconds=self.config.retry_backoff_seconds,
            operation_name="Cloud narration generation",
        )
        return response.content
