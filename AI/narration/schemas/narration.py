from __future__ import annotations

import os
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class NarrationLanguage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language_name: str
    language_tag: str


class NarrationDetailLevel(Enum):
    DETAILED = 18
    STREET = 16
    DISTRICT = 14
    CITY = 10
    COUNTRY = 3


class NarrationSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    latitude: float
    longitude: float
    detail_level: NarrationDetailLevel
    search_radius: int
    language: NarrationLanguage
    user_preferences: str
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    )
    include_narration: bool = True
    photo_count: int = 1
