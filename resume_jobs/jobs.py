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
import math
import re
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

# Candidate's home base: postal code 74078 (Heilbronn). Every reported
# distance is measured from here, not from whichever city a search used.
HOME_POSTAL_CODE = "74078"
HOME_LATLON = (49.1800320, 9.1425113)

# Search plan: home plus the wider Stuttgart / Baden-Württemberg area for
# coverage. NB: omitting umkreis does NOT mean "no limit" — the API then
# defaults to 25 km, so radius_km is always passed for a real radius.
CORRIDOR = ((HOME_POSTAL_CODE, 45), ("Stuttgart", 35))

# The API's Homeoffice filter (arbeitszeit=ho) returns nothing, so remote jobs
# are found by keyword instead.
REMOTE_KEYWORD = "Homeoffice"


def keyword_variants(keyword: Optional[str]) -> list[str]:
    """Return German/English variants for common technical role searches."""
    original = str(keyword or "").strip()
    if not original:
        return []
    lowered = original.lower()
    variants = [original]
    if any(term in lowered for term in (
        "ki", "künstliche intelligenz", "kuenstliche intelligenz",
        "ai entwickler", "ai developer", "ki engineer",
    )):
        variants += ["AI Engineer", "Artificial Intelligence Engineer", "KI Entwickler"]
    if "ai engineer" in lowered or "artificial intelligence engineer" in lowered:
        variants += ["KI Entwickler", "Künstliche Intelligenz Entwickler"]
    if "machine learning" in lowered or "maschinelles lernen" in lowered:
        variants += ["Machine Learning Engineer", "ML Engineer", "Machine Learning Entwickler"]
    if "softwareentwickler" in lowered or "softwareentwicklerin" in lowered:
        variants += ["Software Developer", "Software Engineer"]
    if "dateningenieur" in lowered or "daten engineer" in lowered:
        variants += ["Data Engineer", "Dateningenieur"]
    return list(dict.fromkeys(variant for variant in variants if variant))


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
        if radius_km:
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


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    r = 6371.0088
    lat1, lon1 = a
    lat2, lon2 = b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)), 1)


def annotate_home_distance(
    jobs: Iterable[dict], home: tuple[float, float] = HOME_LATLON
) -> list[dict]:
    """Set each job's `distance_km` to its distance from home.

    The API's own `entfernung` is relative to the search city (and absent for
    a state search), so it is replaced with a value measured from home. Jobs
    without coordinates (e.g. remote) get None.
    """
    jobs = list(jobs)
    for job in jobs:
        lat, lon = job.get("lat"), job.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            job["distance_km"] = haversine_km(home, (lat, lon))
        else:
            job["distance_km"] = None
    return jobs


def search_corridor(
    keyword: Optional[str] = None,
    corridor: Iterable[tuple[str, Optional[int]]] = CORRIDOR,
    remote: bool = False,
    home: tuple[float, float] = HOME_LATLON,
    include_arbeitnow: bool = False,
    arbeitnow_pages: int = 3,
    max_distance_km: Optional[float] = None,
    **kwargs: Any,
) -> list[dict]:
    """Search every corridor entry (plus remote when asked), deduped by id.

    Remote has no location, so it is a nationwide keyword search: the API's
    Homeoffice filter (arbeitszeit=ho) returns no results.

    `include_arbeitnow=True` merges Arbeitnow results in as a second source
    (their ids are namespaced `arbeitnow:<slug>`, so they never collide).
    """
    seen: dict[str, dict] = {}
    corridor = list(corridor)  # iterated twice below

    def merge(jobs: Iterable[dict]) -> None:
        for job in jobs:
            if not job["id"]:
                continue
            if job["id"] not in seen or _closer(job, seen[job["id"]]):
                seen[job["id"]] = job

    keywords = keyword_variants(keyword)
    for search_keyword in keywords or [None]:
        for location, radius in corridor:
            merge(search_once(keyword=search_keyword, location=location, radius_km=radius, **kwargs))

    if remote:
        for search_keyword in keywords or [None]:
            remote_keyword = f"{search_keyword} {REMOTE_KEYWORD}".strip() if search_keyword else REMOTE_KEYWORD
            merge(search_once(keyword=remote_keyword, **kwargs))

    if include_arbeitnow:
        from resume_jobs.arbeitnow import search as arbeitnow_search

        # Arbeitnow has no geo filter; reuse the corridor's city names so results
        # stay in the area (remote jobs are always kept).
        locations = [str(loc) for loc, _ in corridor if not str(loc).isdigit()] + ["Heilbronn"]
        for search_keyword in keywords or [None]:
            merge(arbeitnow_search(keyword=search_keyword, locations=locations, max_pages=arbeitnow_pages))

    annotate_home_distance(seen.values(), home=home)
    jobs = [
        job for job in seen.values()
        if max_distance_km is None
        or job["distance_km"] is None
        or job["distance_km"] <= max_distance_km
    ]
    return sorted(jobs, key=_distance)


def enrich_jobs(
    jobs: list[dict], limit: Optional[int] = None, pause: float = 0.3, http: Any = None
) -> list[dict]:
    """Fetch descriptions for up to `limit` jobs, in place (details are one request each)."""
    http = http or requests.Session()
    for job in jobs if limit is None else jobs[:limit]:
        # Only the Arbeitsagentur search leaves the description out, so only its
        # jobs need (and support) a details request. Other sources already ship
        # a description with the search result.
        if job.get("source") != "arbeitsagentur":
            continue
        if not job.get("id") or job.get("description"):
            continue
        # Details carry no `entfernung` and can even move the point, so keep
        # the search-derived location/distance we already reported.
        keep = {k: job.get(k) for k in ("lat", "lon", "distance_km")}
        try:
            job.update(get_job_details(job["id"], http=http))
            job.update({k: v for k, v in keep.items() if v is not None})
        except Exception as exc:
            job["description_error"] = str(exc)
        if pause:
            time.sleep(pause)
    return jobs


if __name__ == "__main__":
    print("Job search demo — Heilbronn · Stuttgart · Baden-Württemberg (+ remote)")
    print("=" * 60)
    results = search_corridor(keyword="Data Engineer", size=10, remote=True)
    print(f"Found {len(results)} unique jobs\n")
    for job in results[:10]:
        print(f"  [{job['distance_km']} km] {job['title']} @ {job['company']} ({job['location']})")
