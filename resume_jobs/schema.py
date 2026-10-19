"""Profile schema + a defensive normalizer.

`PROFILE_PARAMETERS` is the single source of truth: it is both the LLM tool schema
and the shape `normalize_profile` produces. Factual fields stay language-neutral;
free text reused for interviews / cover letters is emitted in German and English.
"""

CONTACT_KEYS = (
    "email",
    "phone",
    "location",
    "street",
    "postal_code",
    "linkedin",
    "github",
)
SKILL_KEYS = ("technical", "tools", "soft")
EXPERIENCE_KEYS = ("title", "company", "location", "start", "end")
EDUCATION_KEYS = ("degree", "institution", "start", "end")

PROFILE_PARAMETERS = {
    "type": "object",
    "properties": {
        "source_language": {
            "type": "string",
            "description": "Resume body language, ISO 639-1 lowercase, e.g. 'de' or 'en'",
        },
        "name": {"type": "string"},
        "contact": {
            "type": "object",
            "properties": {key: {"type": "string"} for key in CONTACT_KEYS},
            "required": list(CONTACT_KEYS),
        },
        "languages": {
            "type": "array",
            "description": "Language skills, e.g. [{'language':'Deutsch','level':'B2'}]",
            "items": {
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "level": {"type": "string", "description": "CEFR or wording, e.g. B2 / Muttersprache"},
                },
                "required": ["language", "level"],
            },
        },
        "target_roles": {"type": "array", "items": {"type": "string"}},
        "years_experience": {"type": "number", "description": "Relevant years (decimal, 0 if unknown)"},
        "skills": {
            "type": "object",
            "properties": {key: {"type": "array", "items": {"type": "string"}} for key in SKILL_KEYS},
            "required": list(SKILL_KEYS),
        },
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    **{key: {"type": "string"} for key in EXPERIENCE_KEYS},
                    "start": {"type": "string", "description": "Original date text, e.g. 03/2021 or 2020"},
                    "end": {"type": "string", "description": "Original date text or 'heute'/'present'"},
                    "highlights_de": {"type": "array", "items": {"type": "string"}},
                    "highlights_en": {"type": "array", "items": {"type": "string"}},
                },
                "required": list(EXPERIENCE_KEYS) + ["highlights_de", "highlights_en"],
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {key: {"type": "string"} for key in EDUCATION_KEYS},
                "required": list(EDUCATION_KEYS),
            },
        },
        "certifications": {"type": "array", "items": {"type": "string"}},
        "mobility": {"type": "string", "description": "Driver's license / commuting / relocation"},
        "availability": {"type": "string", "description": "Earliest start or availability, e.g. 'ab sofort'"},
        "summary_de": {"type": "string", "description": "One-sentence summary in German"},
        "summary_en": {"type": "string", "description": "One-sentence summary in English"},
    },
    "required": [
        "source_language", "name", "contact", "languages", "target_roles", "years_experience",
        "skills", "experience", "education", "certifications", "mobility", "availability",
        "summary_de", "summary_en",
    ],
}


def emit_profile_tool() -> dict:
    """Build the function tool definition the LLM is forced to call."""
    return {
        "type": "function",
        "function": {
            "name": "emit_profile",
            "description": "Emit the structured candidate profile extracted from the resume (German + English).",
            "parameters": PROFILE_PARAMETERS,
        },
    }


def _strings(value) -> list[str]:
    return [str(x) for x in value] if isinstance(value, list) else []


def _objects(value, keys) -> list[dict]:
    return [
        {key: str(item.get(key) or "") for key in keys}
        for item in value or []
        if isinstance(item, dict)
    ]


def normalize_profile(raw: object) -> dict:
    """Coerce any partial or garbled output into a complete profile (never KeyErrors)."""
    raw = raw if isinstance(raw, dict) else {}
    contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
    skills = raw.get("skills") if isinstance(raw.get("skills"), dict) else {}
    try:
        years = float(raw.get("years_experience"))
    except (TypeError, ValueError):
        years = 0.0

    experience = []
    for item in raw.get("experience") or []:
        if isinstance(item, dict):
            experience.append(
                {
                    **{key: str(item.get(key) or "") for key in EXPERIENCE_KEYS},
                    "highlights_de": _strings(item.get("highlights_de")),
                    "highlights_en": _strings(item.get("highlights_en")),
                }
            )

    return {
        "source_language": str(raw.get("source_language") or ""),
        "name": str(raw.get("name") or ""),
        "contact": {key: str(contact.get(key) or "") for key in CONTACT_KEYS},
        "languages": [
            {"language": str(item.get("language") or ""), "level": str(item.get("level") or "")}
            for item in raw.get("languages") or []
            if isinstance(item, dict)
        ],
        "target_roles": _strings(raw.get("target_roles")),
        "years_experience": years,
        "skills": {key: _strings(skills.get(key)) for key in SKILL_KEYS},
        "experience": experience,
        "education": _objects(raw.get("education"), EDUCATION_KEYS),
        "certifications": _strings(raw.get("certifications")),
        "mobility": str(raw.get("mobility") or ""),
        "availability": str(raw.get("availability") or ""),
        "summary_de": str(raw.get("summary_de") or ""),
        "summary_en": str(raw.get("summary_en") or ""),
    }
