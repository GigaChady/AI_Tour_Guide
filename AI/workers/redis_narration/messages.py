from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LocationEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(min_length=1, description="Tour session identifier")
    lat: float = Field(description="Latitude, accepts numeric strings")
    lng: float = Field(description="Longitude, accepts numeric strings")
    include_photos: int | None = None
    is_narration: bool | None = None

    def __str__(self):
        return f"lat {self.lat} lng {self.lng}"


class PreferencesEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    interests: list[str] | None = None

    def __str__(self):
        return f"{self.interests.__str__()}"


class Poi(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    photos: list[str] = Field(default_factory=list)
    desc: str | None = None
    lat: float
    lng: float


class PoisMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = "pois"
    data: list[Poi] = Field(default_factory=list)


class NarrationMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = "narration"
    text: str


class WorkerResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    narration: NarrationMessage | None = None
    pois: PoisMessage | None = None
