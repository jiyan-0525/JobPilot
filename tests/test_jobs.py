"""Offline tests for the Bundesagentur fuer Arbeit job client.

Uses a FakeSession so no network access is required. Shapes mirror the live v6
search response and v4 details response.
"""
import base64
import urllib.parse

from resume_jobs.jobs import (
    DEFAULT_API_KEY,
    enrich_jobs,
    get_job_details,
    normalize_job,
    search_corridor,
    search_once,
)


def raw_job(ref, title="Data Engineer", company="ACME GmbH", ort="Stuttgart", dist=5, beschreibung=None):
    item = {
        "stellenangebotsart": "ARBEIT",
        "stellenangebotsTitel": title,
        "arbeitszeitVollzeit": True,
        "eintrittszeitraum": {"von": "2026-10-06"},
        "verguetungsangabe": "KEINE_ANGABEN",
        "vertragsdauer": "UNBEFRISTET",
        "stellenlokationen": [
            {
                "adresse": {
                    "strasse": "Tübinger Straße",
                    "hausnummer": "26",
                    "plz": "70178",
                    "ort": ort,
                    "region": "BADEN_WUERTTEMBERG",
                    "land": "DEUTSCHLAND",
                },
                "breite": 48.771,
                "laenge": 9.173,
            }
        ],
        "datumErsteVeroeffentlichung": "2026-06-18",
        "hauptberuf": "Data Engineer",
        "firma": company,
        "referenznummer": ref,
        "entfernung": dist,
        "alleBerufe": ["Data Engineer"],
    }
    if beschreibung is not None:
        item["stellenangebotsBeschreibung"] = beschreibung
    return item


class FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        data, status = self.handler(url, params or {})
        return FakeResponse(data, status)


# ---- normalization ---------------------------------------------------------

def test_normalize_job_maps_fields():
    job = normalize_job(raw_job("10001-1003252000-S"))
    assert job["id"] == "10001-1003252000-S"
    assert job["title"] == "Data Engineer"
    assert job["company"] == "ACME GmbH"
    assert job["location"] == "Stuttgart"
    assert job["postal_code"] == "70178"
    assert job["lat"] == 48.771
    assert job["distance_km"] == 5
    assert job["published"] == "2026-06-18"
    assert job["entry"] == "2026-10-06"
    assert job["url"].endswith("10001-1003252000-S")


def test_normalize_job_handles_missing_location():
    job = normalize_job({"referenznummer": "X-1", "stellenangebotsTitel": "T"})
    assert job["id"] == "X-1"
    assert job["location"] == ""
    assert job["lat"] is None


# ---- search ----------------------------------------------------------------

def test_search_once_builds_params_and_parses():
    session = FakeSession(lambda url, params: ({"ergebnisliste": [raw_job("R-1")]}, 200))
    jobs = search_once(
        keyword="Data Engineer",
        location="Heilbronn",
        radius_km=45,
        offer_types=(1, 4, 34),
        published_within=30,
        http=session,
    )
    assert len(jobs) == 1
    assert jobs[0]["id"] == "R-1"

    call = session.calls[0]
    assert call["url"].endswith("/pc/v6/jobs")
    assert call["params"]["angebotsart"] == "1;4;34"
    assert call["params"]["was"] == "Data Engineer"
    assert call["params"]["wo"] == "Heilbronn"
    assert call["params"]["umkreis"] == 45
    assert call["params"]["veroeffentlichtseit"] == 30
    assert call["headers"]["X-API-Key"] == DEFAULT_API_KEY


def test_search_corridor_dedupes_keeps_smallest_distance():
    def handler(url, params):
        if params.get("wo") == "Heilbronn":
            return {"ergebnisliste": [raw_job("R-1", dist=40), raw_job("R-2", dist=12)]}, 200
        return {"ergebnisliste": [raw_job("R-1", dist=3)]}, 200

    session = FakeSession(handler)
    jobs = search_corridor(keyword="Data Engineer", corridor=(("Heilbronn", 45), ("Stuttgart", 35)), http=session)

    by_id = {job["id"]: job for job in jobs}
    assert set(by_id) == {"R-1", "R-2"}          # deduped across the two searches
    assert by_id["R-1"]["distance_km"] == 3      # smaller distance kept
    assert [job["id"] for job in jobs] == ["R-1", "R-2"]  # sorted by distance


# ---- details ---------------------------------------------------------------

def test_get_job_details_encodes_ref_and_returns_description():
    ref = "10001-1003252000-S"
    expected = urllib.parse.quote(base64.b64encode(ref.encode()).decode())
    session = FakeSession(
        lambda url, params: (raw_job(ref, beschreibung="Full German description text"), 200)
    )
    job = get_job_details(ref, http=session)
    assert job["description"] == "Full German description text"
    assert session.calls[0]["url"].endswith(f"/pc/v4/jobdetails/{expected}")


def test_enrich_jobs_fills_description():
    session = FakeSession(
        lambda url, params: (raw_job("R-1", beschreibung="desc"), 200)
    )
    jobs = [normalize_job(raw_job("R-1")), normalize_job(raw_job("R-2"))]
    enrich_jobs(jobs, limit=1, pause=0, http=session)
    assert jobs[0]["description"] == "desc"
    assert jobs[1]["description"] == ""  # beyond limit, untouched
    assert len(session.calls) == 1
