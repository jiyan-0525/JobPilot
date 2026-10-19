"""Deterministic calculations derived from structured work experience."""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable

_MONTHS = {
    "jan": 1, "january": 1, "januar": 1,
    "feb": 2, "february": 2, "februar": 2,
    "mar": 3, "march": 3, "mär": 3, "märz": 3,
    "apr": 4, "april": 4,
    "may": 5, "mai": 5,
    "jun": 6, "june": 6, "juni": 6,
    "jul": 7, "july": 7, "juli": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "okt": 10, "oktober": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12, "dez": 12, "dezember": 12,
}

_EDUCATION_MARKERS = (
    "student", "studium", "studierende", "universität", "universitaet",
    "university", "hochschule", "college", "master", "bachelor", "phd",
    "promotion", "degree", "ausbildung", "education", "schule",
)


def _is_education_entry(item: dict) -> bool:
    """Exclude education accidentally emitted in the work-experience array."""
    text = " ".join(
        str(item.get(key) or "").lower()
        for key in ("title", "company", "location", "industry", "highlights_de", "highlights_en")
    )
    return any(marker in text for marker in _EDUCATION_MARKERS)


def _month(value: object, today: date | None = None) -> int | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    now = today or date.today()
    if text in {"heute", "present", "current", "now", "ongoing", "aktuell"}:
        return now.year * 12 + now.month
    match = re.search(r"(?P<month>\d{1,2})[./-](?P<year>\d{4})", text)
    if match:
        month, year = int(match.group("month")), int(match.group("year"))
        return year * 12 + month if 1 <= month <= 12 else None
    match = re.search(r"(?P<year>\d{4})[./-](?P<month>\d{1,2})", text)
    if match:
        year, month = int(match.group("year")), int(match.group("month"))
        return year * 12 + month if 1 <= month <= 12 else None
    match = re.fullmatch(r"(?P<month>[a-zäöü]+)\s+(?P<year>\d{4})", text)
    if match and match.group("month") in _MONTHS:
        return int(match.group("year")) * 12 + _MONTHS[match.group("month")]
    match = re.fullmatch(r"\d{4}", text)
    return int(text) * 12 + 1 if match else None


def experience_months(experience: Iterable[dict], today: date | None = None) -> int:
    """Return unique inclusive months covered by dated experience entries."""
    covered: set[int] = set()
    for item in experience:
        if not isinstance(item, dict):
            continue
        if _is_education_entry(item):
            continue
        start = _month(item.get("start"), today)
        end = _month(item.get("end"), today)
        if start is None or end is None or end < start:
            continue
        covered.update(range(start, end + 1))
    return len(covered)


def calculate_years_experience(experience: Iterable[dict], today: date | None = None) -> float:
    """Calculate years from experience dates, counting overlapping months once."""
    return round(experience_months(experience, today) / 12, 1)
