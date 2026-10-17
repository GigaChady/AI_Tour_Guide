from dataclasses import dataclass


@dataclass(frozen=True)
class PlaceLocationConfig:
    max_address_chars: int = 200
    max_place_results: int = 5
    overture_radius_km: float = 20.0
    max_address_range_points: int = 10
    max_tool_alias_queries: int = 1
    max_tool_calls: int = 8
    max_tool_rounds: int = 5

    def __post_init__(self) -> None:
        if min(self.max_address_chars, self.max_place_results, self.overture_radius_km,
               self.max_address_range_points, self.max_tool_alias_queries,
               self.max_tool_calls, self.max_tool_rounds) <= 0:
            raise ValueError("Place location limits must be positive")
        if self.max_place_results > 5:
            raise ValueError("Nominatim supports at most five place results in this adapter")
