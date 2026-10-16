"""Fit analysis: compare a pasted job description against the candidate's resume.

One LLM step (`run_step_tool`) scores how well the parsed profile matches the JD
and splits the requirements into the ones the resume satisfies and the ones it
does not show. The score and both skill lists come back as structure, not prose.
"""
from __future__ import annotations

from typing import Any

from resume_jobs.render import profile_block
from resume_jobs.step import MODEL, run_step_tool

JD_TEXT_LIMIT = 6000
FIT_MAX_TOKENS = 1500

FIT_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_fit_analysis",
        "description": "Score how well the candidate profile matches the job description.",
        "parameters": {
            "type": "object",
            "properties": {
                "score": {"type": "number", "description": "Overall fit, 0-100"},
                "verdict": {
                    "type": "string",
                    "description": "Short label, e.g. 'Strong match', 'Partial match', 'Weak match'",
                },
                "matched_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Job requirements the resume clearly satisfies",
                },
                "missing_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Important job requirements the resume does not show",
                },
                "reason_de": {"type": "string", "description": "One-sentence justification in German"},
                "reason_en": {"type": "string", "description": "One-sentence justification in English"},
            },
            "required": [
                "score",
                "verdict",
                "matched_skills",
                "missing_skills",
                "reason_de",
                "reason_en",
            ],
        },
    },
}


def _score(value: object) -> float:
    """Coerce to a number clamped to 0-100."""
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _strings(value: object) -> list[str]:
    """A list of non-empty strings; a bare string becomes a one-item list."""
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, list):
        value = []
    return [str(x).strip() for x in value if str(x).strip()]


def normalize_fit(raw: object) -> dict:
    """Coerce any partial or garbled output into a complete fit dict."""
    raw = raw if isinstance(raw, dict) else {}
    return {
        "score": _score(raw.get("score")),
        "verdict": str(raw.get("verdict") or "").strip(),
        "matched_skills": _strings(raw.get("matched_skills")),
        "missing_skills": _strings(raw.get("missing_skills")),
        "reason_de": str(raw.get("reason_de") or "").strip(),
        "reason_en": str(raw.get("reason_en") or "").strip(),
    }


def analyze_fit(
    profile: dict, jd_text: str, client: Any = None, model: str = MODEL
) -> dict:
    """LLM step: score the profile against the JD and list matched/missing requirements."""
    result = run_step_tool(
        role="a technical recruiter assessing how well a candidate fits a job",
        task=(
            "Compare the CANDIDATE PROFILE with the JOB DESCRIPTION and give an overall fit "
            "score from 0 to 100, a short verdict, the requirements the candidate clearly "
            "satisfies (matched_skills) and the important ones the profile does not show "
            "(missing_skills), plus a one-sentence justification in German and in English. "
            "Ground every point in the profile — never credit skills the candidate has not shown."
        ),
        expected_output=(
            "score (0-100), verdict, matched_skills, missing_skills, reason_de, reason_en."
        ),
        context=[
            f"CANDIDATE PROFILE\n{profile_block(profile)}",
            f"JOB DESCRIPTION\n{jd_text[:JD_TEXT_LIMIT]}",
        ],
        tool=FIT_TOOL,
        client=client,
        model=model,
        max_tokens=FIT_MAX_TOKENS,
    )
    return normalize_fit(result)
