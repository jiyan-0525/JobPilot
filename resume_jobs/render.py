"""Render profile / job dicts into text blocks for step prompts."""
from __future__ import annotations


def profile_block(profile: dict) -> str:
    """Compact, human-readable rendering of a candidate profile."""
    lines: list[str] = []
    if profile.get("name"):
        lines.append(f"Name: {profile['name']}")
    contact = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
    for label, key in (
        ("Street address", "street"),
        ("Postal code", "postal_code"),
        ("City", "location"),
        ("Phone", "phone"),
        ("Email", "email"),
    ):
        value = contact.get(key)
        if value:
            lines.append(f"{label}: {value}")
    if profile.get("target_roles"):
        lines.append("Target roles: " + ", ".join(profile["target_roles"]))
    years = profile.get("years_experience")
    if years:
        lines.append(f"Years of experience: {years:g}")

    languages = ", ".join(
        f"{item.get('language', '')} ({item.get('level', '')})"
        for item in profile.get("languages", [])
    )
    if languages:
        lines.append("Languages: " + languages)

    skills = profile.get("skills", {}) or {}
    for label, key in (("Technical skills", "technical"), ("Tools", "tools"), ("Soft skills", "soft")):
        if skills.get(key):
            lines.append(f"{label}: " + ", ".join(skills[key]))

    for exp in profile.get("experience", []):
        lines.append(
            f"- {exp.get('title', '')} @ {exp.get('company', '')} "
            f"({exp.get('start', '')}–{exp.get('end', '')})"
        )
        highlights = exp.get("highlights_en") or exp.get("highlights_de") or []
        for point in highlights:
            lines.append(f"    • {point}")

    for edu in profile.get("education", []):
        lines.append(
            f"- {edu.get('degree', '')}, {edu.get('institution', '')} "
            f"({edu.get('start', '')}–{edu.get('end', '')})"
        )

    if profile.get("certifications"):
        lines.append("Certifications: " + ", ".join(profile["certifications"]))
    if profile.get("mobility"):
        lines.append(f"Mobility: {profile['mobility']}")
    if profile.get("availability"):
        lines.append(f"Availability: {profile['availability']}")

    return "\n".join(lines).strip()


def job_block(job: dict, max_description: int = 4000) -> str:
    """Rendering of a normalized job dict, description truncated."""
    parts = [
        f"Job id: {job.get('id', '')}",
        f"Title: {job.get('title', '')}",
        f"Company: {job.get('company', '')}",
        f"Location: {job.get('location', '')} ({job.get('distance_km', '?')} km)",
        f"Offer type: {job.get('offer_type', '')}",
    ]
    if job.get("street"):
        parts.append(f"Company street address: {job['street']}")
    if job.get("postal_code"):
        parts.append(f"Company postal code: {job['postal_code']}")
    description = job.get("description") or ""
    if description:
        parts.append("Description:\n" + description[:max_description])
    return "\n".join(parts)
