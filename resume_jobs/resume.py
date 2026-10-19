"""PDF -> text -> structured profile (step 1).

Uses pypdf for extraction; the extraction itself is one forced tool call via the
shared `step` framing. `client` is injectable so tests run offline.
"""
from __future__ import annotations

import io
from typing import Any, Optional

from resume_jobs.schema import emit_profile_tool, normalize_profile
from resume_jobs.step import MODEL, run_step_tool

EXTRACTION_TASK = """Extract the resume into the structured profile. Rules:
- source_language: the resume body language, 'de' or 'en'.
- target_roles: 1-10 job titles the candidate should apply for (used for job search). For
  German resumes, include the German title and its common English equivalent when applicable,
  e.g. "KI-Entwickler" and "AI Engineer", or "Softwareentwickler" and "Software Developer".
- career_level: assess the candidate as junior, mid, senior, lead, or unknown from demonstrated
  responsibilities. Use evidence from the resume, not title inflation or years alone. Junior
  means mainly learning/contributing with limited independent ownership; senior requires clear
  evidence of independent end-to-end ownership, architecture/technical decisions, mentoring,
  or leadership. If senior evidence is not explicit and substantial, classify as junior or
  unknown, never senior based only on years, skills, or a job title. Include confidence from
  0 to 1 and short evidence items.
- For every experience entry, extract `industry` only when the resume supports it (for example
  software/data, finance, healthcare, retail, manufacturing); otherwise use an empty string.
- Keep the sections strictly separate: `experience` contains paid work, internships, freelance
  work, or volunteering only; `education` contains university, school, degree, and study
  periods. Never copy education into `experience`, even when it has dates.
- `years_experience` is calculated from the dated experience entries by the application. Do not
  estimate or override it independently.
- Preserve original date text (03/2021, 2020, 'seit 2020', 'heute'/'present'); never invent dates.
- summary_de in German, summary_en in English (one sentence each).
- Extract the candidate's postal address, phone number, and email into contact.street,
  contact.postal_code, contact.location, contact.phone, and contact.email when explicitly
  present in the resume. Never infer or invent missing address components.
- Each experience: 2-4 bullets in highlights_de (German) and highlights_en (English).
- Use empty strings/arrays for anything missing; never fabricate.
- Only call emit_profile, and output nothing else."""


def extract_text(source: Any) -> str:
    """Extract plain text from a PDF.

    `source` may be a path, bytes, or a file-like object (e.g. a Streamlit upload).
    A scanned PDF (no text layer) yields an empty string.
    """
    from pypdf import PdfReader

    if isinstance(source, (bytes, bytearray)):
        reader = PdfReader(io.BytesIO(source))
    elif hasattr(source, "read"):
        reader = PdfReader(source)
    else:
        reader = PdfReader(str(source))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()


def parse_profile(text: str, client: Optional[Any] = None) -> dict:
    """Extract resume text into a normalized profile dict.

    `client` defaults to the shared Groq client (needs GROQ_API_KEY).
    """
    raw = run_step_tool(
        role="a resume structuring extractor",
        task=EXTRACTION_TASK,
        expected_output="The complete candidate profile, emitted via emit_profile.",
        context=[text],
        tool=emit_profile_tool(),
        client=client,
        model=MODEL,
        max_tokens=8192,
    )
    profile = normalize_profile(raw)
    if not (profile["name"] or profile["skills"]["technical"] or profile["experience"]):
        raise ValueError("extraction produced an empty profile")
    profile["raw_text"] = text
    return profile
