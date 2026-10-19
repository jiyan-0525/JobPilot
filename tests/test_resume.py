"""Offline tests: PDF extraction + profile normalization + parse_profile
with an injected fake client.

No network, no GROQ_API_KEY required.
"""
import json
from types import SimpleNamespace

import pytest

from resume_jobs import extract_text, parse_profile
from resume_jobs.schema import normalize_profile


def _make_pdf(text: str) -> bytes:
    """Build a minimal single-page PDF that contains a text layer (offline fixture)."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        None,  # content stream, filled in below
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = ("BT /F1 12 Tf 72 720 Td (" + text + ") Tj ET").encode("latin-1")
    objs[3] = (
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"

    xref_pos = len(out)
    n = len(objs) + 1
    out += b"xref\n0 " + str(n).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (
        b"trailer\n<< /Size " + str(n).encode() + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode() + b"\n%%EOF"
    )
    return bytes(out)


VALID_PROFILE = {
    "source_language": "de",
    "name": "Max Mustermann",
    "contact": {
        "email": "max@example.de",
        "phone": "+49 123",
        "location": "Heilbronn",
        "linkedin": "",
        "github": "",
    },
    "languages": [{"language": "Deutsch", "level": "Muttersprache"}],
    "target_roles": ["Data Engineer"],
    "years_experience": 5,
    "skills": {"technical": ["Python", "SQL"], "tools": ["Docker"], "soft": ["Teamarbeit"]},
    "experience": [
        {
            "title": "Data Engineer",
            "company": "ACME GmbH",
            "location": "Stuttgart",
            "start": "03/2021",
            "end": "heute",
            "highlights_de": ["Aufbau einer Datenpipeline"],
            "highlights_en": ["Built a data pipeline"],
        }
    ],
    "education": [
        {"degree": "M.Sc. Informatik", "institution": "Uni Stuttgart", "start": "2015", "end": "2017"}
    ],
    "certifications": [],
    "mobility": "Führerschein Klasse B",
    "availability": "ab sofort",
    "summary_de": "Data Engineer mit 5 Jahren Erfahrung.",
    "summary_en": "Data engineer with 5 years of experience.",
}


class FakeClient:
    """Mimics the OpenAI client: returns preset profiles (or invalid structures) in order."""

    def __init__(self, payloads: list):
        self._payloads = list(payloads)
        self.calls = 0
        self.completions = self  # so client.chat.completions.create uses the same object

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        payload = self._payloads[min(self.calls, len(self._payloads) - 1)]
        self.calls += 1
        tool_call = SimpleNamespace(
            function=SimpleNamespace(name="emit_profile", arguments=json.dumps(payload))
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[tool_call]))]
        )


# ---- PDF extraction --------------------------------------------------------

def test_extract_text_from_pdf():
    pdf = _make_pdf("Max Mustermann - Data Engineer - Python SQL")
    text = extract_text(pdf)
    assert "Max Mustermann" in text
    assert "Python" in text


def test_extract_text_accepts_bytes_and_stream():
    pdf = _make_pdf("Hello")
    import io

    assert "Hello" in extract_text(pdf)
    assert "Hello" in extract_text(io.BytesIO(pdf))


# ---- schema ----------------------------------------------------------------

def test_normalize_profile_fills_defaults():
    out = normalize_profile({})
    assert out["name"] == ""
    assert out["skills"] == {"technical": [], "tools": [], "soft": []}
    assert out["experience"] == []
    assert out["years_experience"] == 0.0
    assert set(out["contact"]) == {
        "email", "phone", "location", "street", "postal_code", "linkedin", "github"
    }


def test_normalize_profile_coerces_bad_types():
    out = normalize_profile({"name": 123, "years_experience": "five", "skills": {"technical": "nope"}})
    assert out["name"] == "123"
    assert out["years_experience"] == 0.0
    assert out["skills"]["technical"] == []


# ---- parse_profile (fake client) -------------------------------------------

def test_parse_profile_valid():
    client = FakeClient([VALID_PROFILE])
    profile = parse_profile("irgendein Lebenslauf", client=client)
    assert profile["name"] == "Max Mustermann"
    assert profile["summary_en"].startswith("Data engineer")
    assert profile["raw_text"] == "irgendein Lebenslauf"
    assert client.calls == 1


def test_parse_profile_raises_on_empty_result():
    client = FakeClient([{}])
    with pytest.raises(ValueError, match="empty profile"):
        parse_profile("text", client=client)
    assert client.calls == 1
