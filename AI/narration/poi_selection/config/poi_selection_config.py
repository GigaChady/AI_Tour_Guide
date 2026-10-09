from pydantic import BaseModel, Field


def _default_category_ranks() -> dict[str, int]:
    return {
        "museum": 1,
        "castle": 1,
        "fort": 1,
        "ruins": 1,
        "attraction": 1,
        "monument": 2,
        "memorial": 2,
        "artwork": 3,
        "viewpoint": 3,
    }


class PoiSelectionConfig(BaseModel):
    distance_weight: float = 5.0
    default_category_rank: int = 99
    wikipedia_bonus: float = 8.0
    wikidata_bonus: float = 5.0
    website_bonus: float = 2.0
    description_bonus: float = 1.0
    planning_result_limit: int = Field(default=5, ge=1)
    seen_key_prefix: str = "poi:seen:"
    seen_ttl_seconds: int = Field(default=7200, ge=1)
    category_ranks: dict[str, int] = Field(default_factory=_default_category_ranks)
