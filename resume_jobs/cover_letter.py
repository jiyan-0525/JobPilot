"""Cover letter / Anschreiben — generated one language at a time.

`write_cover_letter(profile, job, language="en" | "de")` runs a single step and
returns just that language, so German and English are produced (and can be
regenerated) independently.
"""
from __future__ import annotations

from typing import Any

from resume_jobs.render import job_block, profile_block
from resume_jobs.step import MODEL, run_step

ROLE = (
    "a professional application writer helping one candidate apply for one specific job. "
    "Treat the candidate profile, job description, and any user-provided background as factual "
    "sources. Do not invent, exaggerate, or contradict any candidate information."
)

# Instruction per language, written in the target language (better output).
TASKS = {
    "en": (
        "Write a formal business cover letter in English for this job, grounded strictly in the "
        "candidate's real experience.\n\n"
        "Format & Structure (Standard Business Letter):\n"
        "1. Sender header: candidate name, street address, postal code, city, phone, email. Copy every value exactly from the CANDIDATE PROFILE context, especially contact fields; use [Placeholder] only when the field is empty.\n"
        "2. Recipient header: target company name, contact person/department if known, full company address. Copy street, postal code and location exactly from the JOB context; use [Placeholder] only when the field is empty.\n"
        "3. Date and location (e.g., [City], [Date]).\n"
        "4. Subject line (bold): referencing the position.\n"
        "5. Salutation: formal greeting (named contact or hiring team).\n"
        "6. Body (about 250-350 words): opening naming role and company; 2-3 concrete strengths with evidence from resume matching requirements; motivation for the company; willingness to learn for any gaps; closing call to action.\n"
        "7. Professional sign-off and signature line.\n\n"
        "Important: Never claim experience the candidate lacks. Avoid generic clichés."
    ),
    "de": (
        "Schreibe ein vollständiges, formelles Anschreiben auf Deutsch (Niveau C1) im Standard-Geschäftsbriefformat "
        "(DIN 5008) für die gegebene Stelle auf Basis des Profils.\n\n"
        "Formaler Aufbau & Struktur:\n"
        "1. Absenderblock (oben): Name, Anschrift, PLZ Ort, Telefon, E-Mail. Übernimm jedes vorhandene Feld exakt aus dem Kontext CANDIDATE PROFILE; verwende [Platzhalter] nur bei tatsächlich fehlenden Feldern.\n"
        "2. Empfängerblock: Unternehmensname, ggf. Abteilung/Ansprechpartner, vollständige Firmenadresse. Übernimm Straße, PLZ und Ort exakt aus dem Kontext JOB; verwende [Platzhalter] nur bei tatsächlich fehlenden Feldern.\n"
        "3. Ort und Datum (z. B. [Ort], [Aktuelles Datum]).\n"
        "4. Betreffzeile (fett): Bezug zur Position und ggf. Referenznummer (z. B. **Bewerbung als [Stellenbezeichnung]**).\n"
        "5. Textkörper (ca. 250–350 Wörter):\n"
        "   - Formelle Anrede (mit konkretem Namen falls bekannt, sonst 'Sehr geehrte Damen und Herren').\n"
        "   - Einleitung: Bezug auf Position und Unternehmen ohne abgedroschene Floskeln.\n"
        "   - Hauptteil: 2–3 konkrete Stärken mit Belegen, Projekten und Technologien aus dem Lebenslauf passend zu den Anforderungen.\n"
        "   - Motivation für das Unternehmen und die ausgeschriebene Position.\n"
        "   - Zeige Lernbereitschaft und Entwicklungspotenzial, falls Anforderungen nicht vollständig erfüllt werden.\n"
        "   - Schlusssatz mit Handlungsaufforderung (Gesprächsbereitschaft).\n"
        "6. Grußformel & Unterschriftszeile (z. B. 'Mit freundlichen Grüßen', Leerzeilen, Name).\n"
        "7. Anlagenvermerk ('Anlagen').\n\n"
        "Wichtige Regeln:\n"
        "- Verwende ausschließlich Informationen aus dem Lebenslauf. Erfinde keinesfalls Erfahrungen, Kenntnisse oder Zertifikate.\n"
        "- Wenn eine Anforderung nicht im Profil belegt ist, erwähne verwandte Erfahrungen oder Lernbereitschaft; behaupte niemals nicht vorhandene Expertise.\n"
        "- Verwende eine natürliche, selbstbewusste und professionelle Sprache ohne Standardfloskeln."
    ),
}

HEADINGS = {"en": "English (Cover letter)", "de": "Deutsch (Anschreiben)"}


def write_cover_letter(
    profile: dict,
    job: dict,
    language: str = "en",
    client: Any = None,
    model: str = MODEL,
    additional_context: str = "",
) -> str:
    """Return a cover letter in one language ('de' or 'en') as Markdown."""
    language = language.lower()
    if language not in TASKS:
        raise ValueError("language must be 'de' or 'en'")

    context = [
        f"CANDIDATE PROFILE\n{profile_block(profile)}",
        f"JOB\n{job_block(job)}",
    ]
    if additional_context.strip():
        context.append(additional_context.strip())

    return run_step(
        role=ROLE,
        task=TASKS[language],
        expected_output=f"Markdown starting with '## {HEADINGS[language]}'.",
        context=context,
        client=client,
        model=model,
        max_tokens=4000,
    )


def write_cover_letter_from_jd(
    profile: dict,
    jd_text: str,
    language: str = "en",
    personal_background: str = "",
    client: Any = None,
    model: str = MODEL,
) -> str:
    """Return a cover letter from a JD, candidate profile, and optional background."""
    if not isinstance(jd_text, str) or not jd_text.strip():
        raise ValueError("jd_text must be a non-empty string")
    if not profile or not profile_block(profile):
        raise ValueError("a non-empty candidate profile is required")

    if personal_background and not isinstance(personal_background, str):
        raise ValueError("personal_background must be a string")

    job = {
        "title": "",
        "company": "",
        "location": "",
        "offer_type": "",
        "description": jd_text,
    }
    additional_context = ""
    if personal_background.strip():
        additional_context = (
            "CANDIDATE'S USER-PROVIDED ADDITIONAL PERSONAL BACKGROUND\n"
            f"{personal_background.strip()}\n"
            "Use this only when it is consistent with the verified personal background and "
            "candidate profile. "
            "Do not invent or exaggerate any details."
        )

    return write_cover_letter(
        profile,
        job,
        language=language,
        client=client,
        model=model,
        additional_context=additional_context,
    )
