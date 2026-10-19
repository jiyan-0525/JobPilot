"""Offline tests for step 3 (job matching)."""
import json
from types import SimpleNamespace

import pytest

from resume_jobs.match import (
    RANK_MAX_DESCRIPTION,
    RANK_MAX_TOKENS,
    SINGLE_JOB_MAX_DESCRIPTION,
    filter_jobs_for_profile,
    is_senior_level_job,
    senior_candidate_verified,
    prefilter,
    profile_keywords,
    rank_jobs,
    score_job,
)

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


def test_prefilter_prefers_junior_over_senior_when_skills_overlap():
    profile = {**PROFILE, "career_level": {"level": "junior"}}
    jobs = [
        {"id": "senior", "title": "Senior Data Engineer", "description": "Python SQL Docker"},
        {"id": "junior", "title": "Junior Data Engineer", "description": "Python SQL Docker"},
    ]
    assert prefilter(profile, jobs, k=1)[0]["id"] == "junior"


def test_junior_profile_excludes_senior_jobs_from_recommendations():
    profile = {**PROFILE, "career_level": {"level": "junior"}}
    jobs = [
        {"id": "senior", "title": "Senior AI Engineer", "description": ""},
        {"id": "junior", "title": "AI Engineer", "description": ""},
    ]
    assert is_senior_level_job(jobs[0])
    assert [job["id"] for job in filter_jobs_for_profile(profile, jobs)] == ["junior"]


def test_senior_requires_strong_evidence_before_senior_jobs_are_allowed():
    weak_profile = {
        **PROFILE,
        "career_level": {"level": "senior", "confidence": 0.99, "evidence": ["4 years experience"]},
    }
    strong_profile = {
        **PROFILE,
        "career_level": {
            "level": "senior",
            "confidence": 0.9,
            "evidence": ["Owned architecture and mentored the team"],
        },
    }
    jobs = [{"id": "s", "title": "Senior Software Developer", "description": ""}]
    assert not senior_candidate_verified(weak_profile)
    assert filter_jobs_for_profile(weak_profile, jobs) == []
    assert senior_candidate_verified(strong_profile)
    assert filter_jobs_for_profile(strong_profile, jobs) == jobs


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
    task = client.requests[0]["messages"][1]["content"]
    assert "level_fit='too_senior'" in task
    assert "maximum 35" in task


def test_rank_jobs_keeps_request_under_free_tier_tpm():
    """Free tier caps prompt + max_tokens at 8000 tokens/minute (HTTP 413)."""
    jobs = [
        {
            "id": f"j{i}",
            "title": f"Data Engineer {i}",
            "occupation": "Data Engineer",
            "description": "Python SQL Docker Spark Airflow " * 3000,  # deliberately huge
        }
        for i in range(8)
    ]
    client = FakeToolClient({"ranking": []})
    rank_jobs(PROFILE, jobs, client=client, top_n=8, enrich=False)

    prompt = client.requests[0]["messages"][1]["content"]
    assert client.requests[0]["max_tokens"] == RANK_MAX_TOKENS
    # rough token estimate (4 chars ≈ 1 token) must leave headroom under 8000
    assert len(prompt) // 4 + RANK_MAX_TOKENS < 8000
    # descriptions are truncated, not sent whole
    raw = sum(len(job["description"]) for job in jobs)
    assert len(prompt) < raw / 4


def test_score_job_returns_single_fit_entry():
    payload = {
        "ranking": [
            {"job_id": "jd", "score": 72, "matched_skills": ["Python"],
             "missing_skills": ["Kubernetes"], "reason_de": "passt gut", "reason_en": "good fit"},
        ]
    }
    client = FakeToolClient(payload)
    job = {"id": "jd", "title": "Data Engineer", "description": "Python and Kubernetes"}
    fit = score_job(PROFILE, job, client=client)

    assert fit["score"] == 72
    assert fit["missing_skills"] == ["Kubernetes"]
    assert "job" not in fit  # the fit entry, not the ranked wrapper

    # a single JD gets the larger description budget
    user = client.requests[0]["messages"][1]["content"]
    assert "Data Engineer" in user
    assert SINGLE_JOB_MAX_DESCRIPTION > RANK_MAX_DESCRIPTION


def test_score_job_defaults_missing_id():
    payload = {
        "ranking": [
            {"job_id": "jd", "score": 40, "matched_skills": [], "missing_skills": [],
             "reason_de": "d", "reason_en": "e"},
        ]
    }
    client = FakeToolClient(payload)
    fit = score_job(PROFILE, {"title": "X", "description": "y"}, client=client)
    assert fit["score"] == 40


def test_score_job_raises_when_no_result():
    client = FakeToolClient({"ranking": []})
    with pytest.raises(ValueError):
        score_job(PROFILE, {"id": "jd", "title": "X"}, client=client)
