from __future__ import annotations

from typing import Protocol

class SearchClient(Protocol):
    def search(self, query: str) -> str: ...
