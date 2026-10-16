"""Minimal Markdown cleanup for Tavily's extracted page text."""

import re


_IMAGE = re.compile(r"!\[[^\]\n]*\]\([^\)\n]*\)")
_LINK = re.compile(r"\[([^\]\n]*)\]\([^\)\n]*\)")
_LINK_ONLY_LINE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]*)?(?:\[[^\]\n]*\]\([^\)\n]*\)[ \t]*)+$"
)


def clean_extracted_markdown(raw_content: str) -> str:
    """Drop standalone Markdown links and retain link labels inside prose."""
    kept_lines: list[str] = []
    for line in raw_content.splitlines():
        without_images = _IMAGE.sub("", line)
        if _LINK_ONLY_LINE.fullmatch(without_images):
            continue
        if line.strip() and not without_images.strip(" \t-*+"):
            continue
        kept_lines.append(_LINK.sub(r"\1", without_images))
    return "\n".join(kept_lines).strip()
