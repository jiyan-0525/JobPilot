"""Offline tests for the cover letter / Anschreiben step (per-language)."""
from types import SimpleNamespace

import pytest

from resume_jobs.cover_letter import write_cover_letter, write_cover_letter_from_jd

PROFILE = {
    "name": "Alex Beispiel",
    "contact": {
        "street": "Musterstrasse 12",
        "postal_code": "74072",
        "location": "Heilbronn",
        "phone": "+49 170 123456",
        "email": "alex@example.com",
    },
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
    "street": "Industriestrasse 5",
    "postal_code": "70173",
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
    assert "Musterstrasse 12" in user
    assert "Industriestrasse 5" in user
    assert "Copy every value exactly" in user
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


def test_write_cover_letter_from_jd_uses_pasted_description():
    client = FakeTextClient("## English (Cover letter)\nDear ...")
    out = write_cover_letter_from_jd(
        PROFILE,
        "We need Airflow, SQL and cloud cost awareness.",
        personal_background="I am relocating to Stuttgart.",
        client=client,
    )

    assert out.startswith("## English")
    user = client.requests[0]["messages"][1]["content"]
    assert "JOB DESCRIPTION" not in user
    assert "We need Airflow, SQL and cloud cost awareness." in user
    assert "Title:" in user and "Company:" in user
    assert "I am relocating to Stuttgart." in user
    assert "ADDITIONAL PERSONAL BACKGROUND" in user


def test_write_cover_letter_from_jd_rejects_empty_description():
    with pytest.raises(ValueError):
        write_cover_letter_from_jd(PROFILE, "  ", client=FakeTextClient("x"))


def test_write_cover_letter_from_jd_requires_profile():
    with pytest.raises(ValueError, match="candidate profile"):
        write_cover_letter_from_jd({}, "We are hiring a Python developer.", client=FakeTextClient("x"))
