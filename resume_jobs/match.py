"""Step 3 — match a candidate profile against job postings.

Two stages, as plain code:

1. a cheap keyword prefilter picks the shortlist (and we enrich only those with
   their full description — details are one request per job);
2. one LLM step ranks the shortlist (via `run_step_tool`, so the output is a
   structure, not prose).
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from resume_jobs.render import job_block, profile_block
from resume_jobs.step import MODEL, run_step_tool

# Groq's free tier caps a request at 8000 tokens/minute (prompt + max_tokens),
# so the ranking context must stay small: keep descriptions short and the
# completion budget modest.
RANK_MAX_DESCRIPTION = 1000
RANK_MAX_TOKENS = 2000

RANKING_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_ranking",
        "description": "Rank the shortlisted jobs for this candidate, best fit first.",
        "parameters": {
            "type": "object",
            "properties": {
                "ranking": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "The exact 'Job id' value shown for the job in the JOBS context",
                            },
                            "score": {"type": "number", "description": "Fit score, 0-100"},
                            "matched_skills": {"type": "array", "items": {"type": "string"}},
                            "missing_skills": {"type": "array", "items": {"type": "string"}},
                            "reason_de": {"type": "string", "description": "One-sentence reason in German"},
                            "reason_en": {"type": "string", "description": "One-sentence reason in English"},
                        },
                        "required": [
                            "job_id",
                            "score",
                            "matched_skills",
                            "missing_skills",
                            "reason_de",
                            "reason_en",
                        ],
                    },
                }
            },
            "required": ["ranking"],
        },
    },
}


def profile_keywords(profile: dict) -> set[str]:
    """Lowercased skill/role keywords used for the prefilter."""
    skills = profile.get("skills", {}) or {}
    words = list(skills.get("technical", [])) + list(skills.get("tools", []))
    words += profile.get("target_roles", [])
    return {str(w).strip().lower() for w in words if str(w).strip()}


def _job_text(job: dict) -> str:
    return " ".join(
        [job.get("title", ""), job.get("occupation", ""), job.get("description", "")]
    ).lower()


def prefilter(profile: dict, jobs: Iterable[dict], k: int = 8) -> list[dict]:
    """Keep the k jobs with the most keyword overlap (stable, offline)."""
    keywords = profile_keywords(profile)
    scored = []
    for job in jobs:
        text = _job_text(job)
        overlap = sum(1 for word in keywords if word in text)
        scored.append((overlap, job))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [job for _, job in scored[:k]]


def rank_jobs(
    profile: dict,
    jobs: list[dict],
    client: Any = None,
    top_n: int = 8,
    enrich: bool = True,
    http: Any = None,
    model: str = MODEL,
) -> list[dict]:
    """Return the ranked shortlist. Each item is the ranking entry plus its `job`.

    `enrich=True` fetches full descriptions for the shortlist first (one request
    per job) so the ranking sees the real requirements. Set it False in tests.
    """
    shortlist = [dict(job) for job in prefilter(profile, jobs, k=top_n)]

    if enrich:
        from resume_jobs.jobs import enrich_jobs

        enrich_jobs(shortlist, http=http)

    result = run_step_tool(
        role="a technical recruiter matching a candidate to job postings",
        task=(
            "Score each shortlisted job for this candidate from 0 to 100, based on how well "
            "the candidate's real skills and experience match the job's requirements. List the "
            "skills that match and the important ones the candidate lacks. Give a one-sentence "
            "reason in German and in English. Rank the jobs, best fit first. For each job set "
            "job_id to the exact 'Job id' value shown in the JOBS context — copy it verbatim."
        ),
        expected_output=(
            "A `ranking` array covering every shortlisted job_id, best fit first, each with "
            "score, matched_skills, missing_skills, reason_de, reason_en."
        ),
        context=[
            f"CANDIDATE PROFILE\n{profile_block(profile)}",
            "JOBS\n"
            + "\n\n".join(
                job_block(job, max_description=RANK_MAX_DESCRIPTION) for job in shortlist
            ),
        ],
        tool=RANKING_TOOL,
        client=client,
        model=model,
        max_tokens=RANK_MAX_TOKENS,
    )

    by_id = {job["id"]: job for job in shortlist}

    def resolve(raw_id: object) -> Optional[dict]:
        if raw_id in by_id:
            return by_id[raw_id]
        # Fallback: the model echoed a title/company string instead of the exact id.
        text = str(raw_id or "").lower()
        for job in shortlist:
            title = (job.get("title") or "").lower()
            if title and title in text:
                return job
        return None

    ranked: list[dict] = []
    for entry in result.get("ranking", []):
        job = resolve(entry.get("job_id"))
        if job is None:
            continue
        ranked.append({**entry, "job": job, "job_id": job["id"]})
    return ranked
