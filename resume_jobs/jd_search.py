"""Find jobs from a pasted job description (JD).

The JD itself is the query, in two steps:

1. an LLM step extracts the search parameters (roles / skills / location) from
   the JD text;
2. the same sources as tab 2 are searched (Arbeitsagentur + Arbeitnow), a cheap
   keyword prefilter takes a shortlist, and one LLM step ranks the shortlist by
   similarity to the JD.

`find_jobs_from_jd` ties both steps together and returns the query, the raw
candidate jobs, and the ranked shortlist.
"""
from __future__ import annotations

from typing import Any, Optional

from resume_jobs.match import prefilter
from resume_jobs.render import job_block
from resume_jobs.step import MODEL, run_step_tool

# Keep the ranking context small on Groq's free tier (see match.py).
JD_MAX_DESCRIPTION = 1000
JD_MAX_TOKENS = 2000
JD_TEXT_LIMIT = 6000

JD_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_jd_query",
        "description": "Extract the job-search parameters from a job description.",
        "parameters": {
            "type": "object",
            "properties": {
                "roles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Job titles / search keywords, most relevant first (1-4 items)",
                },
                "skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key required skills and tools named in the description",
                },
                "location": {
                    "type": "string",
                    "description": "Work location / city if the description states one, else empty",
                },
                "language": {"type": "string", "description": "Job description language: 'de' or 'en'"},
                "seniority": {
                    "type": "string",
                    "description": "junior, mid, senior or lead if stated, else empty",
                },
            },
            "required": ["roles", "skills", "location", "language", "seniority"],
        },
    },
}

JD_RANKING_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_jd_ranking",
        "description": "Rank the candidate jobs by similarity to the target job description.",
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
                            "score": {
                                "type": "number",
                                "description": "Similarity to the target JD (role, seniority, skills, domain), 0-100",
                            },
                            "reason_de": {"type": "string", "description": "One-sentence reason in German"},
                            "reason_en": {"type": "string", "description": "One-sentence reason in English"},
                        },
                        "required": ["job_id", "score", "reason_de", "reason_en"],
                    },
                }
            },
            "required": ["ranking"],
        },
    },
}


def normalize_query(raw: object) -> dict:
    """Coerce the extracted query into a complete dict (never KeyErrors)."""
    raw = raw if isinstance(raw, dict) else {}

    def strings(value: object) -> list[str]:
        if isinstance(value, str):
            value = [value]  # a bare string is one item, not one char per item
        elif not isinstance(value, list):
            value = []
        return [str(x).strip() for x in value if str(x).strip()]

    return {
        "roles": strings(raw.get("roles")),
        "skills": strings(raw.get("skills")),
        "location": str(raw.get("location") or "").strip(),
        "language": str(raw.get("language") or "").strip(),
        "seniority": str(raw.get("seniority") or "").strip(),
    }


def extract_jd_query(jd_text: str, client: Any = None, model: str = MODEL) -> dict:
    """LLM step: derive search roles / skills / location from the JD text."""
    result = run_step_tool(
        role="a recruiter deriving a job search from a job advertisement",
        task=(
            "Read the JOB DESCRIPTION and extract the job titles to search for (most "
            "relevant first), the key required skills and tools, the work location if it "
            "states one, the language, and the seniority if stated. Use only what the "
            "description actually says."
        ),
        expected_output=(
            "roles (1-4 search titles), skills, location, language, and seniority."
        ),
        context=[f"JOB DESCRIPTION\n{jd_text[:JD_TEXT_LIMIT]}"],
        tool=JD_QUERY_TOOL,
        client=client,
        model=model,
        max_tokens=800,
    )
    return normalize_query(result)


def _pseudo_profile(query: dict) -> dict:
    """Shape the query like a profile so match.prefilter can be reused."""
    return {
        "skills": {"technical": list(query.get("skills", [])), "tools": []},
        "target_roles": list(query.get("roles", [])),
    }


def rank_jobs_against_jd(
    jd_text: str,
    jobs: list[dict],
    query: dict,
    top_n: int = 8,
    enrich: bool = True,
    client: Any = None,
    http: Any = None,
    model: str = MODEL,
) -> list[dict]:
    """Return the ranked shortlist. Each item is the ranking entry plus its `job`."""
    shortlist = [dict(job) for job in prefilter(_pseudo_profile(query), jobs, k=top_n)]

    if enrich:
        from resume_jobs.jobs import enrich_jobs

        enrich_jobs(shortlist, http=http)

    result = run_step_tool(
        role="a technical recruiter comparing job postings to a target job description",
        task=(
            "Score each shortlisted job from 0 to 100 for how similar it is to the TARGET "
            "JOB DESCRIPTION (same role, seniority, skills and domain). Rank the jobs, best "
            "match first. For each job set job_id to the exact 'Job id' value shown in the "
            "JOBS context — copy it verbatim."
        ),
        expected_output=(
            "A `ranking` array covering every shortlisted job_id, best match first, each "
            "with score, reason_de, reason_en."
        ),
        context=[
            f"TARGET JOB DESCRIPTION\n{jd_text[:JD_TEXT_LIMIT]}",
            "JOBS\n"
            + "\n\n".join(
                job_block(job, max_description=JD_MAX_DESCRIPTION) for job in shortlist
            ),
        ],
        tool=JD_RANKING_TOOL,
        client=client,
        model=model,
        max_tokens=JD_MAX_TOKENS,
    )

    by_id = {job["id"]: job for job in shortlist}
    ranked: list[dict] = []
    for entry in result.get("ranking", []):
        job = by_id.get(entry.get("job_id"))
        if job is None:
            continue
        ranked.append({**entry, "job": job, "job_id": job["id"]})
    return ranked


def find_jobs_from_jd(
    jd_text: str,
    *,
    client: Any = None,
    http: Any = None,
    top_n: int = 8,
    size: int = 50,
    include_arbeitnow: bool = True,
    model: str = MODEL,
) -> dict:
    """Extract a query from the JD, search the corridor, and rank the matches.

    Returns ``{"query", "keyword", "jobs", "ranked"}``.
    """
    query = extract_jd_query(jd_text, client=client, model=model)
    keyword = (
        query["roles"][0]
        if query["roles"]
        else (" ".join(query["skills"][:2]) or None)
    )

    from resume_jobs.jobs import CORRIDOR, search_corridor

    corridor = list(CORRIDOR)
    if query["location"]:
        # also search the JD's own city, on top of the home corridor
        corridor = [(query["location"], 40)] + corridor

    jobs = search_corridor(
        keyword=keyword,
        corridor=corridor,
        remote=True,
        include_arbeitnow=include_arbeitnow,
        size=size,
        http=http,
    )
    ranked = rank_jobs_against_jd(
        jd_text, jobs, query, top_n=top_n, client=client, http=http, model=model
    )
    return {"query": query, "keyword": keyword, "jobs": jobs, "ranked": ranked}
