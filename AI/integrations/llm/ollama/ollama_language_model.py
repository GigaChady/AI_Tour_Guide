from __future__ import annotations

from typing import Any


class OllamaLanguageModel:
    def __init__(self, config: Any):
        from langchain_ollama import ChatOllama

        model_options = {
            "model": config.model_name,
            "temperature": config.temperature,
            "top_k": config.top_k,
            "top_p": config.top_p,
            "num_predict": config.num_predict,
            "base_url": config.base_url,
        }
        if hasattr(config, "format"):
            model_options["format"] = config.format
        if hasattr(config, "repeat_penalty"):
            model_options["repeat_penalty"] = config.repeat_penalty
        self.model = ChatOllama(**model_options)

    def generate(self, messages: list[tuple[str, str]]) -> str:
        from langchain_core.prompts import ChatPromptTemplate

        chain = ChatPromptTemplate.from_messages(messages) | self.model
        return chain.invoke({}).content
