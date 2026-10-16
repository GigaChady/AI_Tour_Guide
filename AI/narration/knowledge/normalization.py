from __future__ import annotations

import re
import unicodedata


def normalized_name(value: str) -> str:
    """Normalize spelling, without discarding meaningful words."""
    # NFKD does not transliterate Polish ł/Ł.
    value = value.casefold().replace("ł", "l")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"[\W_]+", " ", value, flags=re.UNICODE).strip()


def normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def normalized_street(value: str) -> str:
    words = normalized_name(value).split()
    if words and words[0] in {"ul", "ulica"}:
        words.pop(0)
    return " ".join(words)
