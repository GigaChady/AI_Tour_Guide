from __future__ import annotations

from dataclasses import dataclass

import requests

from narration.knowledge.address_evidence import SupportedAddress, normalized_address_street
from narration.knowledge.models import GeocodedPlace
from narration.knowledge.normalization import normalized_name


@dataclass(frozen=True)
class GusAddressConfig:
    endpoint: str = "https://geo.stat.gov.pl/api/fts/gc/pkt"
    timeout_seconds: int = 15

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("Address timeout must be positive")


class GusAddressClient:
    """Use GUS reference address points, never a street centroid."""

    def __init__(self, config: GusAddressConfig | None = None, *, session=None):
        self.config = config or GusAddressConfig()
        self.session = session or requests.Session()

    def search_address(
        self, address: SupportedAddress, *, country: str = ""
    ) -> list[GeocodedPlace]:
        if country and normalized_name(country) not in {"polska", "poland"}:
            return []
        response = self.session.post(
            self.config.endpoint,
            json={"reqs": [{
                "miejsc_nazwa": address.city,
                "ul_pelna": address.street,
                "pkt_numer": address.house_number,
            }], "useExtServiceIfNotFound": False},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("GUS address response is not a list")
        results: list[GeocodedPlace] = []
        for item in payload:
            if not isinstance(item, dict) or not isinstance(item.get("single"), dict):
                continue
            point = item["single"]
            city_names = (
                point.get("miejsc_nazwa"), point.get("miejsc_pelna"),
                point.get("pow_nazwa"),
            )
            if normalized_name(address.city) not in {
                normalized_name(str(name)) for name in city_names if name
            }:
                continue
            if (normalized_address_street(str(point.get("ul_pelna") or ""))
                    != normalized_address_street(address.street)):
                continue
            if normalized_name(str(point.get("pkt_numer") or "")) != normalized_name(address.house_number):
                continue
            geometry = point.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []
            if geometry.get("type") != "Point" or len(coordinates) < 2:
                continue
            identifier = point.get("id")
            if identifier is None:
                continue
            try:
                results.append(GeocodedPlace(
                    name=f"{address.street} {address.house_number}",
                    lat=float(coordinates[1]), lon=float(coordinates[0]),
                    coordinate_source=f"gus_address:{identifier}",
                    city=address.city, country="Polska", street=address.street,
                    house_number=address.house_number, location_type="address",
                    external_ids={"gus_address": str(identifier)},
                ))
            except (TypeError, ValueError):
                continue
        return results
