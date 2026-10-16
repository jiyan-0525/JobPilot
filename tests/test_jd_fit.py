"""Offline tests for the JD-vs-resume fit analysis."""
import json
from types import SimpleNamespace

from resume_jobs.jd_fit import analyze_fit, normalize_fit

PROFILE = {
    "name": "Alex Beispiel",
    "target_roles": ["Data Engineer"],
    "years_experience": 5,
    "skills": {"technical": ["Python", "SQL"], "tools": ["Docker"], "soft": []},
    "languages": [{"language": "German", "level": "C1"}],
    "experience": [],
    "education": [],
    "certifications": [],
}

JD = "Data Engineer wanted. Must know Python, SQL, Spark and AWS."


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


def test_normalize_fit_clamps_score_and_wraps_strings():
    fit = normalize_fit({"score": 150, "matched_skills": "Python", "missing_skills": ["Spark", ""]})
    assert fit["score"] == 100.0                # clamped to 0-100
    assert fit["matched_skills"] == ["Python"]  # bare string wraps, not char-splits
    assert fit["missing_skills"] == ["Spark"]   # blanks dropped
    assert fit["verdict"] == ""


def test_normalize_fit_handles_garbage():
    fit = normalize_fit(None)
    assert fit["score"] == 0.0
    assert fit["matched_skills"] == []
    assert fit["reason_en"] == ""


def test_analyze_fit_returns_structured_analysis():
    payload = {
        "score": 72,
        "verdict": "Partial match",
        "matched_skills": ["Python", "SQL"],
        "missing_skills": ["Spark", "AWS"],
        "reason_de": "Gute Basis, aber Spark fehlt.",
        "reason_en": "Good base, but Spark is missing.",
    }
    client = FakeToolClient(payload)
    fit = analyze_fit(PROFILE, JD, client=client)

    assert fit["score"] == 72.0
    assert fit["verdict"] == "Partial match"
    assert fit["missing_skills"] == ["Spark", "AWS"]

    # both the profile and the JD reached the prompt, via the fit tool
    request = client.requests[0]
    assert request["tool_choice"]["function"]["name"] == "emit_fit_analysis"
    user = request["messages"][1]["content"]
    assert "CANDIDATE PROFILE" in user and "Data Engineer" in user
    assert "JOB DESCRIPTION" in user and "Spark" in user
