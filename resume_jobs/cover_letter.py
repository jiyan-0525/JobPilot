"""Cover letter / Anschreiben — generated one language at a time.

`write_cover_letter(profile, job, language="en" | "de")` runs a single step and
returns just that language, so German and English are produced (and can be
regenerated) independently.
"""
from __future__ import annotations

from typing import Any

from resume_jobs.render import job_block, profile_block
from resume_jobs.step import MODEL, run_step

ROLE = "a professional application writer helping one candidate apply for one specific job"

# Instruction per language, written in the target language (better output).
TASKS = {
    "en": (
        "Write a cover letter in English for this job, grounded strictly in the candidate's real "
        "experience. Include: a professional greeting and sign-off; an opening naming the role and "
        "company; 2-3 concrete strengths with evidence taken from the resume that match the job's "
        "requirements; motivation for the company; and a closing call to action. Never claim "
        "experience the candidate lacks. About 250-350 words."
    ),
    "de": (
        "Schreibe ein Anschreiben auf Deutsch für diese Stelle, ausschließlich auf Basis der echten "
        "Erfahrungen der Person. Enthalte: eine professionelle Anrede und Grußformel; eine Einleitung "
        "mit Stelle und Unternehmen; 2-3 konkrete Stärken mit Belegen aus dem Lebenslauf, die zu den "
        "Anforderungen passen; Motivation für das Unternehmen; und einen Abschluss mit "
        "Handlungsaufforderung. Behaupte keine Erfahrung, die nicht vorhanden ist. Etwa 250-350 Wörter."
    ),
}

HEADINGS = {"en": "English (Cover letter)", "de": "Deutsch (Anschreiben)"}


def write_cover_letter(
    profile: dict, job: dict, language: str = "en", client: Any = None, model: str = MODEL
) -> str:
    """Return a cover letter in one language ('de' or 'en') as Markdown."""
    language = language.lower()
    if language not in TASKS:
        raise ValueError("language must be 'de' or 'en'")

    return run_step(
        role=ROLE,
        task=TASKS[language],
        expected_output=f"Markdown starting with '## {HEADINGS[language]}'.",
        context=[
            f"CANDIDATE PROFILE\n{profile_block(profile)}",
            f"JOB\n{job_block(job)}",
        ],
        client=client,
        model=model,
        max_tokens=4000,
    )


def write_cover_letter_from_jd(
    profile: dict,
    jd_text: str,
    language: str = "en",
    client: Any = None,
    model: str = MODEL,
) -> str:
    """Return a cover letter from a pasted job description and candidate profile."""
    if not isinstance(jd_text, str) or not jd_text.strip():
        raise ValueError("jd_text must be a non-empty string")
    if not profile or not profile_block(profile):
        raise ValueError("a non-empty candidate profile is required")

    return write_cover_letter(
        profile,
        {
            "title": "",
            "company": "",
            "location": "",
            "offer_type": "",
            "description": jd_text,
        },
        language=language,
        client=client,
        model=model,
    )
