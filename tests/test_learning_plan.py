"""Offline tests for the fit-check learning plan."""
from types import SimpleNamespace

from resume_jobs.learning_plan import build_learning_plan

PROFILE = {
    "name": "Alex Beispiel",
    "target_roles": ["Data Engineer"],
    "years_experience": 5,
    "skills": {"technical": ["Python", "SQL"], "tools": ["Airflow"], "soft": []},
    "languages": [{"language": "German", "level": "C1"}],
    "experience": [
        {"title": "Data Engineer", "company": "Technik GmbH", "start": "03/2021", "end": "heute",
         "highlights_en": ["Built Airflow pipelines"], "highlights_de": ["Airflow-Pipelines gebaut"]}
    ],
    "education": [],
    "certifications": [],
}

JOB = {
    "id": "jd",
    "title": "Senior Data Engineer (m/w/d)",
    "company": "BCM Solutions GmbH",
    "location": "Stuttgart",
    "offer_type": "ARBEIT",
    "description": "We need Kubernetes, Terraform and Airflow on AWS.",
}


class FakeTextClient:
    def __init__(self, text):
        self.text = text
        self.requests = []
        self.completions = self

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        message = SimpleNamespace(content=self.text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_build_learning_plan_includes_profile_job_and_gaps():
    client = FakeTextClient("## Deutsch\n...\n## English\n...")
    out = build_learning_plan(PROFILE, JOB, gaps=["Kubernetes", "Terraform"], client=client)
    assert out.startswith("## Deutsch")

    user = client.requests[0]["messages"][1]["content"]
    assert "CANDIDATE PROFILE" in user and "Alex Beispiel" in user
    assert "JOB" in user and "BCM Solutions GmbH" in user
    assert "IDENTIFIED GAPS" in user and "Kubernetes" in user and "Terraform" in user
    # bilingual instruction reached the prompt
    assert "German and English" in user


def test_build_learning_plan_without_gaps_omits_gap_block():
    client = FakeTextClient("x")
    build_learning_plan(PROFILE, JOB, client=client)
    user = client.requests[0]["messages"][1]["content"]
    assert "IDENTIFIED GAPS" not in user
