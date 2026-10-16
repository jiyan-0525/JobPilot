"""Offline tests for step 4 (interview preparation)."""
from types import SimpleNamespace

from resume_jobs.interview import prepare_interview

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
    "id": "10001-x",
    "title": "Senior Data Engineer (m/w/d)",
    "company": "BCM Solutions GmbH",
    "location": "Stuttgart",
    "distance_km": 1,
    "offer_type": "ARBEIT",
    "description": "We need Airflow, SQL and cloud cost awareness (FinOps).",
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


def test_prepare_interview_includes_profile_and_job():
    client = FakeTextClient("## Deutsch\n...\n## English\n...")
    out = prepare_interview(PROFILE, JOB, client=client)
    assert out.startswith("## Deutsch")

    user = client.requests[0]["messages"][1]["content"]
    assert "CANDIDATE PROFILE" in user and "Alex Beispiel" in user
    assert "JOB" in user and "BCM Solutions GmbH" in user
    # bilingual + no-fabrication instruction reached the prompt
    assert "BOTH German and English" in user or "German and English" in user


def test_prepare_interview_optional_question_bank():
    client = FakeTextClient("x")
    prepare_interview(PROFILE, JOB, client=client, question_bank=["What is dbt?"])
    user = client.requests[0]["messages"][1]["content"]
    assert "QUESTION BANK" in user and "What is dbt?" in user
