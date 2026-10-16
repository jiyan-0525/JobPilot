"""Step 4 — interview preparation in German + English, grounded in the resume.

One LLM step (role / task / expected_output / context).
An optional question bank (e.g. from rag.py) can be passed as extra context.
"""
from __future__ import annotations

import os
from typing import Any, Optional, Sequence

from resume_jobs.render import job_block, profile_block
from resume_jobs.step import MODEL, run_step

ROLE = "a senior technical interviewer preparing one candidate for one specific job"

TASK = (
    "Produce interview material in BOTH German and English, grounded strictly in the candidate's "
    "real experience. For each language include: (1) 6-10 likely interview questions, each with a "
    "short answer outline the candidate can actually defend; (2) a gap analysis listing the job's "
    "important requirements the candidate does not clearly meet; (3) 3 questions the candidate "
    "should ask the interviewer. Never claim experience the candidate lacks."
)

EXPECTED_OUTPUT = (
    "Markdown with two clearly separated sections, '## Deutsch' and '## English'. Each section "
    "contains 'Questions' (with answer outlines), 'Gap analysis', and 'Questions to ask'."
)

DEFAULT_QUESTION_BANK_FOLDER = "question_bank"


def gather_question_bank(
    query: str, folder: str = DEFAULT_QUESTION_BANK_FOLDER, k: int = 3
) -> list[str]:
    """Retrieve question-bank snippets via rag.py, or [] when the folder is absent."""
    if not os.path.isdir(folder):
        return []
    try:
        from rag import KnowledgeBase  # project-root module

        return [hit["text"] for hit in KnowledgeBase(folder).search(query, k=k)]
    except Exception:
        return []


def prepare_interview(
    profile: dict,
    job: dict,
    client: Any = None,
    question_bank: Optional[Sequence[str]] = None,
    model: str = MODEL,
) -> str:
    """Return bilingual interview material as Markdown."""
    context = [
        f"CANDIDATE PROFILE\n{profile_block(profile)}",
        f"JOB\n{job_block(job)}",
    ]
    if question_bank:
        context.append("QUESTION BANK (optional reference material)\n" + "\n\n".join(question_bank))

    return run_step(
        role=ROLE,
        task=TASK,
        expected_output=EXPECTED_OUTPUT,
        context=context,
        client=client,
        model=model,
        max_tokens=6000,
    )
