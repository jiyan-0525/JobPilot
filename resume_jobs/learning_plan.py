"""Fit check — turn a job's gaps into a focused learning plan.

The fit *score* comes from `resume_jobs.match.score_job`; this module turns the
identified gaps into an actionable study plan with one LLM step.

`build_learning_plan(profile, job, gaps=None)` returns bilingual (DE + EN)
Markdown, grounded in the candidate's real profile and the job's requirements.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from resume_jobs.render import job_block, profile_block
from resume_jobs.step import MODEL, run_step

ROLE = "a technical career coach building a focused study plan for one candidate and one job"

TASK = (
    "The candidate is applying for this job. From the job's requirements and the candidate's "
    "real profile, identify the knowledge and skills the candidate most needs to strengthen for "
    "THIS role, then turn them into an actionable learning plan. Produce it in BOTH German and "
    "English. In each language include: (1) 'Zu stärken' / 'To strengthen' — the prioritised "
    "gaps, each with a one-line reason it matters for this job; (2) 'Lernplan' / 'Learning plan' "
    "— ordered, time-boxed steps, each naming the topic, what to learn, and a concrete practice "
    "or resource type, followed by a short overall timeline. Ground everything in the candidate's "
    "real experience and the job's requirements. Never claim the candidate already has a skill "
    "they lack, and never invent job requirements that are not in the posting."
)

EXPECTED_OUTPUT = (
    "Markdown with two clearly separated sections, '## Deutsch' and '## English'. Each section "
    "contains 'Zu stärken'/'To strengthen' (prioritised gaps) and 'Lernplan'/'Learning plan' "
    "(ordered, time-boxed steps plus a short timeline)."
)


def build_learning_plan(
    profile: dict,
    job: dict,
    gaps: Optional[Sequence[str]] = None,
    client: Any = None,
    model: str = MODEL,
) -> str:
    """Return a bilingual learning plan as Markdown.

    `gaps` is the fit check's `missing_skills`; when given it is passed as extra
    context so the plan targets exactly the identified gaps.
    """
    context = [
        f"CANDIDATE PROFILE\n{profile_block(profile)}",
        f"JOB\n{job_block(job)}",
    ]
    if gaps:
        context.append(
            "IDENTIFIED GAPS (from the fit check)\n" + "\n".join(f"- {gap}" for gap in gaps)
        )

    return run_step(
        role=ROLE,
        task=TASK,
        expected_output=EXPECTED_OUTPUT,
        context=context,
        client=client,
        model=model,
        max_tokens=6000,
    )
