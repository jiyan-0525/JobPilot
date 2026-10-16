"""Second job source: Arbeitnow's public job-board API (free, no key).

GET /api/job-board-api?page=N -> {"data": [...]}, 300 jobs per page, newest
first. The API has no server-side keyword filter (`search`/`q` are ignored), so
pages are fetched and filtered client-side. Jobs are returned in the same shape
as the Arbeitsagentur client, with namespaced ids (`arbeitnow:<slug>`) so they
can be merged and ranked alongside Arbeitsagentur jobs.
"""
from __future__ import annotations

import html
import re
import time
from typing import Any, Optional

import requests

BASE_URL = "https://www.arbeitnow.com/api/job-board-api"
TIMEOUT = 15
RETRIES = 2
# Each page carries 300 jobs with full HTML descriptions, so keep the cap low.
MAX_PAGES = 3

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    """Strip HTML tags, decode entities and tidy the whitespace."""
    text = _TAG_RE.sub(" ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


def _published(created_at: Any) -> str:
    try:
        return time.strftime("%Y-%m-%d", time.localtime(int(created_at)))
    except (TypeError, ValueError, OSError):
        return str(created_at or "")


def normalize_job(item: dict) -> dict:
    """Map a raw Arbeitnow item into the shared job dict shape."""
    slug = item.get("slug") or ""
    job_types = item.get("job_types") or []
    tags = item.get("tags") or []
    return {
        "source": "arbeitnow",
        "id": f"arbeitnow:{slug}" if slug else "",
        "title": item.get("title") or "",
        "company": item.get("company_name") or "",
        "location": item.get("location") or "",
        "postal_code": "",
        "region": "",
        "street": "",
        "lat": None,
        "lon": None,
        "distance_km": None,
        "published": _published(item.get("created_at")),
        "entry": "",
        "offer_type": ", ".join(job_types),
        "full_time": None,
        "salary": "",
        "contract": ", ".join(job_types),
        "occupation": ", ".join(tags),
        "url": item.get("url") or "",
        "description": _clean(item.get("description")),
        "remote": bool(item.get("remote")),
    }


def _get_page(page: int, http: Any) -> list[dict]:
    """GET one page of the board with retries, re-raising on the last attempt."""
    headers = {"Accept": "application/json"}
    for attempt in range(RETRIES + 1):
        try:
            response = http.get(BASE_URL, params={"page": page}, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json().get("data") or []
        except Exception:
            if attempt == RETRIES:
                raise
            time.sleep(0.5 * (attempt + 1))


def search(
    keyword: Optional[str] = None,
    locations: Optional[list[str]] = None,
    remote_only: bool = False,
    max_pages: int = MAX_PAGES,
    size: Optional[int] = None,
    http: Any = None,
) -> list[dict]:
    """Fetch pages and return normalized jobs matching every keyword word.

    `locations` keeps jobs whose location contains one of the given terms (or
    that are remote) — Arbeitnow has no server-side geo filter, and its board is
    Europe-wide, so this is how the corridor stays focused.
    """
    http = http or requests.Session()
    words = [w for w in re.split(r"\s+", (keyword or "").lower()) if w]
    terms = [t.lower() for t in (locations or []) if t]

    found: list[dict] = []
    for page in range(1, max_pages + 1):
        items = _get_page(page, http)
        if not items:
            break
        for item in items:
            job = normalize_job(item)
            if not job["id"]:
                continue
            if remote_only and not job["remote"]:
                continue
            if terms and not job["remote"] and not any(t in job["location"].lower() for t in terms):
                continue
            if words:
                # Match against title + tags only (not the description): the
                # description mentions everything, which floods the results.
                haystack = f"{job['title']} {job['occupation']}".lower()
                if not all(word in haystack for word in words):
                    continue
            found.append(job)
        if size and len(found) >= size:
            break
    return found[:size] if size else found
