"""Job search via the Bundesagentur fuer Arbeit Jobsuche API.

Official, free, no registration: a public key goes in the X-API-Key header.
Verified against the live API:
- search  GET /pc/v6/jobs                                 -> {"ergebnisliste": [...]}
- details GET /pc/v4/jobdetails/{base64(referenznummer)}  -> full description
Search results carry no description, so details are one request per job (N+1):
enrich only a limited, cached subset. Filters like angebotsart are
semicolon-separated and really do union ("1;4;34" = ARBEIT + AUSBILDUNG + Trainee).
"""
from __future__ import annotations

import base64
import time
import urllib.parse
from typing import Any, Iterable, Optional

import requests

DEFAULT_API_KEY = "jobboerse-jobsuche"
BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
DETAIL_PAGE_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{}"
TIMEOUT = 15
RETRIES = 2

# 1 = ARBEIT, 2 = SELBSTAENDIGKEIT, 4 = AUSBILDUNG, 34 = PRAKTIKUM/Trainee
DEFAULT_OFFER_TYPES = (1, 4, 34)

# Heilbronn Baden-Württemberg corridor: two radius searches, merged and deduped.
CORRIDOR = (("Heilbronn", 45), ("Stuttgart", 35))


def _csv(values: Any) -> str:
    """A value or iterable -> the API's semicolon-separated form."""
    return str(values) if isinstance(values, (str, int)) else ";".join(map(str, values))


def _get(path: str, params: dict, http: Any) -> dict:
    """GET with retries, re-raising on the final attempt."""
    url = BASE_URL + path
    headers = {"X-API-Key": DEFAULT_API_KEY, "Accept": "application/json"}
    for attempt in range(RETRIES + 1):
        try:
            response = http.get(url, params=params, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt == RETRIES:
                raise
            time.sleep(0.5 * (attempt + 1))


def normalize_job(item: dict) -> dict:
    """Map a raw v6 search / v4 details item into a stable job dict."""
    ref = item.get("referenznummer") or ""
    locations = item.get("stellenlokationen") or []
    location = locations[0] if locations and isinstance(locations[0], dict) else {}
    address = location.get("adresse") or {}
    return {
        "source": "arbeitsagentur",
        "id": ref,
        "title": item.get("stellenangebotsTitel") or "",
        "company": item.get("firma") or "",
        "location": address.get("ort") or "",
        "postal_code": address.get("plz") or "",
        "region": address.get("region") or "",
        "street": " ".join(p for p in (address.get("strasse"), address.get("hausnummer")) if p),
        "lat": location.get("breite"),
        "lon": location.get("laenge"),
        "distance_km": item.get("entfernung"),
        "published": item.get("datumErsteVeroeffentlichung") or "",
        "entry": (item.get("eintrittszeitraum") or {}).get("von") or "",
        "offer_type": item.get("stellenangebotsart") or "",
        "full_time": item.get("arbeitszeitVollzeit"),
        "salary": item.get("verguetungsangabe") or "",
        "contract": item.get("vertragsdauer") or "",
        "occupation": item.get("hauptberuf") or "",
        "url": DETAIL_PAGE_URL.format(ref) if ref else "",
        "description": item.get("stellenangebotsBeschreibung") or "",
    }


def search_once(
    keyword: Optional[str] = None,
    location: Optional[str] = None,
    radius_km: int = 25,
    offer_types: Any = DEFAULT_OFFER_TYPES,
    worktime: Any = None,
    published_within: Optional[int] = None,
    size: int = 50,
    http: Any = None,
) -> list[dict]:
    """Run one search request; return normalized jobs."""
    http = http or requests.Session()
    params: dict = {"size": size, "angebotsart": _csv(offer_types)}
    if keyword:
        params["was"] = keyword
    if location:
        params["wo"] = location
        params["umkreis"] = radius_km
    if worktime:
        params["arbeitszeit"] = _csv(worktime)
    if published_within:
        params["veroeffentlichtseit"] = published_within

    items = _get("/pc/v6/jobs", params, http).get("ergebnisliste") or []
    return [normalize_job(item) for item in items]


def get_job_details(refnr: str, http: Any = None) -> dict:
    """Full details (including the description) for one job."""
    http = http or requests.Session()
    encoded = urllib.parse.quote(base64.b64encode(refnr.encode()).decode())
    return normalize_job(_get(f"/pc/v4/jobdetails/{encoded}", {}, http))


def _closer(candidate: dict, current: dict) -> bool:
    new, old = candidate.get("distance_km"), current.get("distance_km")
    return isinstance(new, (int, float)) and (not isinstance(old, (int, float)) or new < old)


def _distance(job: dict) -> float:
    value = job.get("distance_km")
    return value if isinstance(value, (int, float)) else float("inf")


def search_corridor(
    keyword: Optional[str] = None,
    corridor: Iterable[tuple[str, int]] = CORRIDOR,
    **kwargs: Any,
) -> list[dict]:
    """Search every city and merge results, deduped by id (smallest distance kept)."""
    seen: dict[str, dict] = {}
    for location, radius in corridor:
        for job in search_once(keyword=keyword, location=location, radius_km=radius, **kwargs):
            if not job["id"]:
                continue
            if job["id"] not in seen or _closer(job, seen[job["id"]]):
                seen[job["id"]] = job
    return sorted(seen.values(), key=_distance)


def enrich_jobs(
    jobs: list[dict], limit: Optional[int] = None, pause: float = 0.3, http: Any = None
) -> list[dict]:
    """Fetch descriptions for up to `limit` jobs, in place (details are one request each)."""
    http = http or requests.Session()
    for job in jobs if limit is None else jobs[:limit]:
        if not job.get("id") or job.get("description"):
            continue
        try:
            job.update(get_job_details(job["id"], http=http))
        except Exception as exc:
            job["description_error"] = str(exc)
        if pause:
            time.sleep(pause)
    return jobs


if __name__ == "__main__":
    print("Job search demo — Heilbronn Baden-Württemberg corridor")
    print("=" * 60)
    results = search_corridor(keyword="Data Engineer", size=10)
    print(f"Found {len(results)} unique jobs\n")
    for job in results[:10]:
        print(f"  [{job['distance_km']} km] {job['title']} @ {job['company']} ({job['location']})")
