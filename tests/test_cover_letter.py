"""Offline tests for the cover letter / Anschreiben step (per-language)."""
from types import SimpleNamespace

import pytest

from resume_jobs.cover_letter import write_cover_letter

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
    "description": "We need Airflow, SQL and cloud cost awareness.",
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


def test_write_cover_letter_english():
    client = FakeTextClient("## English (Cover letter)\nDear ...")
    out = write_cover_letter(PROFILE, JOB, language="en", client=client)
    assert out.startswith("## English")

    user = client.requests[0]["messages"][1]["content"]
    assert "CANDIDATE PROFILE" in user and "Alex Beispiel" in user
    assert "JOB" in user and "BCM Solutions GmbH" in user
    assert "in English" in user


def test_write_cover_letter_german():
    client = FakeTextClient("## Deutsch (Anschreiben)\nSehr geehrte ...")
    out = write_cover_letter(PROFILE, JOB, language="de", client=client)
    assert out.startswith("## Deutsch")

    user = client.requests[0]["messages"][1]["content"]
    assert "auf Deutsch" in user
    assert "Anschreiben" in user


def test_write_cover_letter_rejects_unknown_language():
    with pytest.raises(ValueError):
        write_cover_letter(PROFILE, JOB, language="fr", client=FakeTextClient("x"))
