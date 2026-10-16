"""Offline tests for step 3 (job matching)."""
import json
from types import SimpleNamespace

from resume_jobs.match import prefilter, profile_keywords, rank_jobs

PROFILE = {
    "name": "Alex Beispiel",
    "target_roles": ["Data Engineer"],
    "years_experience": 5,
    "skills": {"technical": ["Python", "SQL"], "tools": ["Docker"], "soft": ["Mentoring"]},
    "languages": [{"language": "German", "level": "C1"}],
    "experience": [],
    "education": [],
    "certifications": [],
}

JOBS = [
    {"id": "a", "title": "Data Engineer (m/w/d)", "occupation": "Data Engineer", "description": ""},
    {"id": "b", "title": "Koch (m/w/d)", "occupation": "Koch", "description": ""},
    {"id": "c", "title": "Python Developer", "occupation": "Softwareentwickler", "description": ""},
]


class FakeToolClient:
    """Mimics the OpenAI client returning a forced tool call."""

    def __init__(self, payload):
        self.payload = payload
        self.requests = []
        self.completions = self

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        name = kwargs["tool_choice"]["function"]["name"]
        tool_call = SimpleNamespace(
            function=SimpleNamespace(name=name, arguments=json.dumps(self.payload))
        )
        message = SimpleNamespace(tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_profile_keywords_lowercased():
    keywords = profile_keywords(PROFILE)
    assert {"python", "sql", "docker", "data engineer"} <= keywords


def test_prefilter_keeps_relevant_and_drops_irrelevant():
    ids = [job["id"] for job in prefilter(PROFILE, JOBS, k=2)]
    assert "b" not in ids          # cook has no overlap
    assert set(ids) == {"a", "c"}


def test_rank_jobs_attaches_job_and_drops_unknown_ids():
    payload = {
        "ranking": [
            {"job_id": "a", "score": 90, "matched_skills": ["Python", "SQL"],
             "missing_skills": ["Spark"], "reason_de": "passt", "reason_en": "fits"},
            {"job_id": "zzz", "score": 10, "matched_skills": [], "missing_skills": [],
             "reason_de": "?", "reason_en": "?"},
        ]
    }
    client = FakeToolClient(payload)
    ranked = rank_jobs(PROFILE, JOBS, client=client, top_n=5, enrich=False)

    assert ranked[0]["job"]["id"] == "a"
    assert ranked[0]["score"] == 90
    assert all(entry["job_id"] in {"a", "b", "c"} for entry in ranked)  # "zzz" dropped
    assert len(ranked) == 1

    # the shortlist and profile reached the prompt
    user = client.requests[0]["messages"][1]["content"]
    assert "CANDIDATE PROFILE" in user and "Data Engineer" in user
    assert "JOBS" in user and "Python Developer" in user
