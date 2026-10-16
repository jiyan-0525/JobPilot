"""Offline tests for finding jobs from a pasted job description."""
import json
from types import SimpleNamespace

from resume_jobs.jd_search import (
    extract_jd_query,
    find_jobs_from_jd,
    normalize_query,
    rank_jobs_against_jd,
)

# ---- fakes -----------------------------------------------------------------

class FakeToolClient:
    """Returns a different forced-tool payload per tool name."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.requests = []
        self.completions = self

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        name = kwargs["tool_choice"]["function"]["name"]
        tool_call = SimpleNamespace(
            function=SimpleNamespace(name=name, arguments=json.dumps(self.payloads[name]))
        )
        message = SimpleNamespace(tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def raw_job(ref, title="Data Engineer", beschreibung=""):
    item = {
        "stellenangebotsart": "ARBEIT",
        "stellenangebotsTitel": title,
        "firma": "ACME GmbH",
        "referenznummer": ref,
        "stellenlokationen": [
            {"adresse": {"ort": "Stuttgart", "plz": "70178"}, "breite": 48.771, "laenge": 9.173}
        ],
    }
    if beschreibung:
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
    def __init__(self, jobs):
        self.jobs = jobs
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(url)
        if "jobdetails" in url:
            return FakeResponse(raw_job("R-1", beschreibung="Full description"))
        return FakeResponse({"ergebnisliste": self.jobs})


JD = "We are hiring a Data Engineer. You will build pipelines with Python and SQL."

# ---- query extraction ------------------------------------------------------

def test_normalize_query_coerces_partial_output():
    q = normalize_query({"roles": ["Data Engineer", ""], "skills": "Python"})
    assert q["roles"] == ["Data Engineer"]      # blanks dropped
    assert q["skills"] == ["Python"]            # a bare string wraps, not char-splits
    assert q["location"] == "" and q["seniority"] == ""


def test_extract_jd_query_uses_the_tool():
    client = FakeToolClient({
        "emit_jd_query": {
            "roles": ["Data Engineer"], "skills": ["Python", "SQL"],
            "location": "Stuttgart", "language": "en", "seniority": "mid",
        }
    })
    query = extract_jd_query(JD, client=client)
    assert query["roles"] == ["Data Engineer"]
    assert query["skills"] == ["Python", "SQL"]
    assert query["location"] == "Stuttgart"
    # the JD reached the prompt
    assert "JOB DESCRIPTION" in client.requests[0]["messages"][1]["content"]

# ---- ranking ---------------------------------------------------------------

def test_rank_jobs_against_jd_attaches_job_and_drops_unknown_ids():
    jobs = [
        {"id": "R-1", "title": "Data Engineer", "occupation": "Data Engineer", "description": "Python SQL"},
        {"id": "R-2", "title": "Koch", "occupation": "Koch", "description": ""},
    ]
    query = {"roles": ["Data Engineer"], "skills": ["Python"]}
    client = FakeToolClient({
        "emit_jd_ranking": {"ranking": [
            {"job_id": "R-1", "score": 88, "reason_de": "passt", "reason_en": "fits"},
            {"job_id": "zzz", "score": 5, "reason_de": "?", "reason_en": "?"},
        ]}
    })
    ranked = rank_jobs_against_jd(JD, jobs, query, client=client, enrich=False)
    assert [r["job"]["id"] for r in ranked] == ["R-1"]
    assert ranked[0]["score"] == 88
    user = client.requests[0]["messages"][1]["content"]
    assert "TARGET JOB DESCRIPTION" in user and "JOBS" in user

# ---- end to end (offline) --------------------------------------------------

def test_find_jobs_from_jd_orchestrates_offline():
    client = FakeToolClient({
        "emit_jd_query": {"roles": ["Data Engineer"], "skills": ["Python"], "location": ""},
        "emit_jd_ranking": {"ranking": [
            {"job_id": "R-1", "score": 90, "reason_de": "sehr passend", "reason_en": "great fit"},
        ]},
    })
    session = FakeSession([raw_job("R-1")])
    result = find_jobs_from_jd(JD, client=client, http=session, include_arbeitnow=False)

    assert result["keyword"] == "Data Engineer"
    assert result["query"]["roles"] == ["Data Engineer"]
    assert result["ranked"][0]["job"]["id"] == "R-1"
    # two LLM steps (query + ranking) happened
    names = [r["tool_choice"]["function"]["name"] for r in client.requests]
    assert names == ["emit_jd_query", "emit_jd_ranking"]
