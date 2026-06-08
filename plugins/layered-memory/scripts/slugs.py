"""Slug normalization (spec §9). Stdlib only."""
import re

_MAX = 50


def normalize_slug(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("_", "-").replace(" ", "-")
    s = re.sub(r"[^a-z0-9-]+", "-", s)   # any other char -> dash
    s = re.sub(r"-{2,}", "-", s).strip("-")
    s = s[:_MAX].strip("-")
    return s or "unsorted"
