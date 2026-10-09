from __future__ import annotations

from integrations.llm.nvidia.config import NvidiaConfig
from shared.retry import call_with_timeout_retry


class NvidiaLanguageModel:
    def __init__(self, config: NvidiaConfig | None = None):
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        self.config = config or NvidiaConfig()
        self.model = ChatNVIDIA(
            model=self.config.model_name,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_tokens=self.config.max_tokens,
        )

    def generate(self, messages: list[tuple[str, str]]) -> str:
        from langchain_core.prompts import ChatPromptTemplate

        chain = ChatPromptTemplate.from_messages(messages) | self.model
        response = call_with_timeout_retry(
            lambda: chain.invoke({}),
            timeout_seconds=self.config.request_timeout_seconds,
            max_retries=self.config.max_retries,
            backoff_seconds=self.config.retry_backoff_seconds,
            operation_name="Cloud narration generation",
        )
        return response.content
