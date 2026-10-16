from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NarrationDetailLevel(Enum):
    DETAILED = 18
    STREET = 16
    DISTRICT = 14
    CITY = 10
    COUNTRY = 3


class LocationAddress(BaseModel):
    raw: dict[str, Any] = Field(default_factory=dict)
