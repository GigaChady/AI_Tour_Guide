from __future__ import annotations

import re
from dataclasses import dataclass

from narration.knowledge.normalization import normalized_name


_NUMBER = re.compile(r"(?<!\w)(\d{1,4}[a-zA-Z]?)$")
_RANGE = re.compile(r"\d\s*[-–—/]\s*\d")
_STREET_PREFIX = re.compile(
    r"^(?:ul\.?|ulica|al\.?|aleja|aleje|pl\.?|plac|os\.?|osiedle)\s+",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class SupportedAddress:
    street: str
    house_number: str
    city: str


def normalized_address_street(value: str) -> str:
    return normalized_name(_STREET_PREFIX.sub("", value.strip()).strip())


def supported_address(
    address: str, *, city: str, source_text: str, max_chars: int
) -> tuple[SupportedAddress | None, str]:
    """Accept only a single numbered address present in the research text."""
    value = address.strip()
    if not value:
        return None, "empty address"
    if len(value) > max_chars or "@" in value or "http" in value.casefold() or ";" in value:
        return None, "invalid address format"
    if not city.strip():
        return None, "place city is missing"
    street_part, separator, city_part = value.partition(",")
    if separator and normalized_name(city) not in normalized_name(city_part):
        return None, "address city differs from place city"
    if _RANGE.search(street_part):
        return None, "multiple house numbers"
    match = _NUMBER.search(street_part.strip())
    if match is None:
        return None, "house number is missing"
    street = _STREET_PREFIX.sub("", street_part[:match.start()].strip()).strip()
    number = match.group(1)
    street_key = normalized_name(street)
    if len(street_key) < 3:
        return None, "street or square name is missing"
    source_key = f" {normalized_name(source_text)} "
    phrase = f" {street_key} {normalized_name(number)} "
    if phrase not in source_key:
        return None, "street and house number were not found together in source text"
    if re.search(r"^\d{1,4}(?:\s|$)", source_key.split(phrase, 1)[1]):
        return None, "source text lists multiple house numbers"
    return SupportedAddress(street=street, house_number=number, city=city), "supported"
