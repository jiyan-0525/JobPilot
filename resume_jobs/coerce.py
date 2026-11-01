"""Defensive coercion helpers for LLM output.

Forced tool calls return JSON, but the model can still emit a string where a
number belongs, a bare string instead of a list, or an unknown enum value.
Every consumer normalizes before it renders, so a bad generation degrades to a
sane default instead of crashing the UI.
"""
from __future__ import annotations

from typing import Iterable


def score_0_100(value: object) -> float:
    """Coerce to a number clamped to 0-100."""
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def string_list(value: object) -> list[str]:
    """A list of non-empty strings; a bare string becomes a one-item list."""
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, list):
        value = []
    return [str(item).strip() for item in value if str(item).strip()]


def choice(value: object, allowed: Iterable[str], default: str) -> str:
    """Lowercased value when it is one of `allowed`, otherwise `default`."""
    text = str(value or "").strip().lower()
    return text if text in set(allowed) else default
