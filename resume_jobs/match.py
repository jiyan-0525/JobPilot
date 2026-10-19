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
# A single pasted JD has room for its full text; the multi-job path must stay small.
SINGLE_JOB_MAX_DESCRIPTION = 4000

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
                            "job_level": {
                                "type": "string",
                                "enum": ["intern", "junior", "mid", "senior", "lead", "unknown"],
                                "description": "Seniority explicitly required or evidenced by the posting",
                            },
                            "level_fit": {
                                "type": "string",
                                "enum": ["good", "stretch", "too_senior", "unknown"],
                                "description": "Whether the job level fits the candidate; use too_senior for a clear mismatch",
                            },
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


def is_senior_level_job(job: dict) -> bool:
    """Return whether a posting explicitly targets senior-level ownership."""
    text = _job_text(job)
    markers = (
        "senior", "lead", "principal", "staff engineer", "teamleitung",
        "team lead", "technical lead", "tech lead", "fachliche führung",
        "fachliche leitung", "leitung eines teams",
    )
    return any(marker in text for marker in markers)


def senior_candidate_verified(profile: dict) -> bool:
    """Allow senior recommendations only with strong, explicit resume evidence."""
    career_level = profile.get("career_level") or {}
    if not isinstance(career_level, dict):
        return False
    if str(career_level.get("level") or "").lower() != "senior":
        return False
    try:
        confidence = float(career_level.get("confidence", 0))
    except (TypeError, ValueError):
        return False
    evidence = " ".join(str(item).lower() for item in career_level.get("evidence") or [])
    markers = (
        "end-to-end", "end to end", "architecture", "architect",
        "technical decision", "mentoring", "mentor", "led a team",
        "team lead", "leadership", "technical lead", "verantwort",
        "architektur", "teamleitung", "geführt",
    )
    return confidence >= 0.85 and any(marker in evidence for marker in markers)


def filter_jobs_for_profile(profile: dict, jobs: Iterable[dict]) -> list[dict]:
    """Exclude senior postings unless seniority is strongly verified."""
    if senior_candidate_verified(profile):
        return list(jobs)
    return [job for job in jobs if not is_senior_level_job(job)]


def _level_bias(profile: dict, job: dict) -> int:
    """Prefer jobs at the candidate's level during the offline shortlist step."""
    if senior_candidate_verified(profile):
        return 0
    text = _job_text(job)
    if any(marker in text for marker in ("lead", "director", "head of", "principal")):
        return -120
    if "senior" in text:
        return -100
    if any(marker in text for marker in ("junior", "entry-level", "entry level", "trainee")):
        return 20
    return 0


def prefilter(profile: dict, jobs: Iterable[dict], k: int = 8) -> list[dict]:
    """Keep the k jobs with the most keyword overlap (stable, offline)."""
    jobs = filter_jobs_for_profile(profile, jobs)
    keywords = profile_keywords(profile)
    scored = []
    for job in jobs:
        text = _job_text(job)
        overlap = sum(1 for word in keywords if word in text)
        scored.append((overlap + _level_bias(profile, job), job))
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
    max_description: int = RANK_MAX_DESCRIPTION,
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
            "First determine the candidate's career level from demonstrated responsibilities in "
            "the CANDIDATE PROFILE. Do not equate years or a previous title with seniority. "
            "Then classify each job's level from explicit wording such as Junior, Senior, Lead, "
            "or from clearly senior responsibilities. Score each shortlisted job from 0 to 100 "
            "based on real skills, experience, and level fit. A job clearly above the candidate's "
            "level must be marked level_fit='too_senior' and receive a low score (maximum 35), "
            "even when skills overlap. Prefer junior roles for junior candidates; do not "
            "recommend senior/lead roles merely because the keywords match. List matching skills "
            "and important missing skills. Give a one-sentence reason in German and English. "
            "Rank the jobs, best fit first. For each job set job_id to the exact 'Job id' value "
            "shown in the JOBS context — copy it verbatim."
        ),
        expected_output=(
            "A `ranking` array covering every shortlisted job_id, best fit first. Each entry "
            "must include job_level, level_fit, score, matched_skills, missing_skills, "
            "reason_de, and reason_en."
        ),
        context=[
            f"CANDIDATE PROFILE\n{profile_block(profile)}",
            "JOBS\n"
            + "\n\n".join(
                job_block(job, max_description=max_description) for job in shortlist
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


def score_job(
    profile: dict,
    job: dict,
    client: Any = None,
    model: str = MODEL,
) -> dict:
    """Fit-check a single job posting (e.g. an uploaded JD).

    Wraps `rank_jobs` for one job and returns just the fit entry:
    `{job_id, score, matched_skills, missing_skills, reason_de, reason_en}`.
    A posting with no `id` gets the placeholder `"jd"` so the ranking can resolve it.
    """
    job = {**job, "id": job.get("id") or "jd"}
    ranked = rank_jobs(
        profile,
        [job],
        client=client,
        top_n=1,
        enrich=False,
        model=model,
        max_description=SINGLE_JOB_MAX_DESCRIPTION,
    )
    if not ranked:
        raise ValueError("fit check returned no result for the job")
    entry = dict(ranked[0])
    entry.pop("job", None)
    return entry
