from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OverpassResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    elements: list[dict[str, Any]] = Field(default_factory=list)
