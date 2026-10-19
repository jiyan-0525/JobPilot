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
FIT_MAX_TOKENS = 4000

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
                "job_level": {
                    "type": "string",
                    "enum": ["intern", "junior", "mid", "senior", "lead", "unknown"],
                    "description": "Seniority explicitly required or evidenced by the job description",
                },
                "level_fit": {
                    "type": "string",
                    "enum": ["good", "stretch", "too_senior", "unknown"],
                    "description": "Whether the job level fits the candidate",
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
                "learning_plan": {
                    "type": "array",
                    "description": (
                        "What the candidate should learn to become competitive for this job, "
                        "most important first. Only cover gaps identified in missing_skills."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "skill": {"type": "string", "description": "Skill / topic to learn"},
                            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                            "why": {
                                "type": "string",
                                "description": "Why it matters for this specific job (grounded in the JD)",
                            },
                            "how": {
                                "type": "string",
                                "description": "Concrete way to learn it: topics to study, practice project, resource type",
                            },
                            "effort": {
                                "type": "string",
                                "description": "Rough effort to become job-ready, e.g. '1-2 weeks'",
                            },
                        },
                        "required": ["skill", "priority", "why", "how", "effort"],
                    },
                },
            },
            "required": [
                "score",
                "verdict",
                "job_level",
                "level_fit",
                "matched_skills",
                "missing_skills",
                "reason_de",
                "reason_en",
                "learning_plan",
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


def _plan(value: object) -> list[dict]:
    """Coerce the learning plan into a clean list of steps (drops empty entries)."""
    steps: list[dict] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or "").strip()
        if not skill:
            continue
        priority = str(item.get("priority") or "").strip().lower()
        steps.append(
            {
                "skill": skill,
                "priority": priority if priority in ("high", "medium", "low") else "medium",
                "why": str(item.get("why") or "").strip(),
                "how": str(item.get("how") or "").strip(),
                "effort": str(item.get("effort") or "").strip(),
            }
        )
    return steps


def normalize_fit(raw: object) -> dict:
    """Coerce any partial or garbled output into a complete fit dict."""
    raw = raw if isinstance(raw, dict) else {}
    return {
        "score": _score(raw.get("score")),
        "verdict": str(raw.get("verdict") or "").strip(),
        "job_level": str(raw.get("job_level") or "unknown").strip().lower(),
        "level_fit": str(raw.get("level_fit") or "unknown").strip().lower(),
        "matched_skills": _strings(raw.get("matched_skills")),
        "missing_skills": _strings(raw.get("missing_skills")),
        "reason_de": str(raw.get("reason_de") or "").strip(),
        "reason_en": str(raw.get("reason_en") or "").strip(),
        "learning_plan": _plan(raw.get("learning_plan")),
    }


def learning_plan_markdown(fit: dict, job_title: str = "") -> str:
    """Render a fit dict as a Markdown learning plan (for display or download)."""
    title = f"# Learning plan — {job_title}" if job_title else "# Learning plan"
    lines = [title, "", f"Fit score: **{fit.get('score', 0):.0f}/100** — {fit.get('verdict', '')}", ""]
    if fit.get("missing_skills"):
        lines += ["**Gaps to close:** " + ", ".join(fit["missing_skills"]), ""]
    for i, step in enumerate(fit.get("learning_plan", []), start=1):
        lines.append(f"## {i}. {step['skill']}  _{step['priority']} priority_")
        if step["why"]:
            lines.append(f"- **Why:** {step['why']}")
        if step["how"]:
            lines.append(f"- **How:** {step['how']}")
        if step["effort"]:
            lines.append(f"- **Effort:** {step['effort']}")
        lines.append("")
    return "\n".join(lines).strip()


def analyze_fit(
    profile: dict, jd_text: str, client: Any = None, model: str = MODEL
) -> dict:
    """LLM step: score the profile against the JD and list matched/missing requirements."""
    result = run_step_tool(
        role="a technical recruiter assessing how well a candidate fits a job",
        task=(
            "Compare the CANDIDATE PROFILE with the JOB DESCRIPTION. First assess the candidate's "
            "career level from demonstrated scope, not years or titles alone, and classify the "
            "job level. Give an overall fit "
            "score from 0 to 100, a short verdict, the requirements the candidate clearly "
            "satisfies (matched_skills) and the important ones the profile does not show "
            "(missing_skills), plus a one-sentence justification in German and in English. "
            "Then, assuming the candidate wants to apply for this job, produce a practical "
            "learning_plan that closes those gaps, most important first: for each item give "
            "the skill, a priority (high/medium/low), why it matters for this job, how to "
            "learn it, and a rough effort estimate. Ground every point in the profile and the "
            "job description — never credit skills the candidate has not shown. If the job is "
            "clearly above the candidate's level, set level_fit='too_senior' and cap the score "
            "at 35; do not hide this mismatch behind overlapping keywords."
        ),
        expected_output=(
            "job_level, level_fit, score (0-100), verdict, matched_skills, missing_skills, "
            "reason_de, reason_en, and a learning_plan of prioritized steps (skill, priority, "
            "why, how, effort)."
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
