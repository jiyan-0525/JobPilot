"""Offline tests for the JD-vs-resume fit analysis."""
import json
from types import SimpleNamespace

from resume_jobs.jd_fit import analyze_fit, learning_plan_markdown, normalize_fit

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
    assert fit["learning_plan"] == []


def test_normalize_fit_coerces_learning_plan():
    fit = normalize_fit({"learning_plan": [
        {"skill": "Spark", "priority": "HIGH", "why": "w", "how": "h", "effort": "2 weeks"},
        {"skill": "", "priority": "high"},        # dropped: no skill
        "not a dict",                              # dropped
        {"skill": "AWS", "priority": "weird"},     # invalid priority -> medium
    ]})
    assert [step["skill"] for step in fit["learning_plan"]] == ["Spark", "AWS"]
    assert fit["learning_plan"][0]["priority"] == "high"    # lowercased
    assert fit["learning_plan"][1]["priority"] == "medium"  # invalid -> medium


def test_learning_plan_markdown_lists_steps():
    fit = normalize_fit({
        "score": 60, "verdict": "Partial match", "missing_skills": ["Spark"],
        "learning_plan": [{"skill": "Spark", "priority": "high", "why": "core skill",
                           "how": "build a pipeline", "effort": "2 weeks"}],
    })
    md = learning_plan_markdown(fit, job_title="Data Engineer")
    assert "Learning plan — Data Engineer" in md
    assert "Spark" in md and "build a pipeline" in md and "2 weeks" in md


def test_analyze_fit_returns_structured_analysis():
    payload = {
        "score": 72,
        "verdict": "Partial match",
        "matched_skills": ["Python", "SQL"],
        "missing_skills": ["Spark", "AWS"],
        "reason_de": "Gute Basis, aber Spark fehlt.",
        "reason_en": "Good base, but Spark is missing.",
        "learning_plan": [
            {"skill": "Spark", "priority": "high", "why": "core of the role",
             "how": "build an ETL project", "effort": "2-3 weeks"},
        ],
    }
    client = FakeToolClient(payload)
    fit = analyze_fit(PROFILE, JD, client=client)

    assert fit["score"] == 72.0
    assert fit["verdict"] == "Partial match"
    assert fit["missing_skills"] == ["Spark", "AWS"]
    assert fit["learning_plan"][0]["skill"] == "Spark"

    # both the profile and the JD reached the prompt, via the fit tool
    request = client.requests[0]
    assert request["tool_choice"]["function"]["name"] == "emit_fit_analysis"
    user = request["messages"][1]["content"]
    assert "CANDIDATE PROFILE" in user and "Data Engineer" in user
    assert "JOB DESCRIPTION" in user and "Spark" in user
