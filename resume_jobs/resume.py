"""PDF -> text -> structured profile (step 1).

Uses pypdf for extraction; the extraction itself is one forced tool call via the
shared `step` framing. `client` is injectable so tests run offline.
"""
from __future__ import annotations

import io
from typing import Any, Optional

from resume_jobs.schema import emit_profile_tool, normalize_profile
from resume_jobs.step import MODEL, run_step_tool

EXTRACTION_TASK = """Extract the resume into the structured profile. Rules:
- source_language: the resume body language, 'de' or 'en'.
- target_roles: 1-10 job titles the candidate should apply for (used for job search).
- Preserve original date text (03/2021, 2020, 'seit 2020', 'heute'/'present'); never invent dates.
- summary_de in German, summary_en in English (one sentence each).
- Each experience: 2-4 bullets in highlights_de (German) and highlights_en (English).
- Use empty strings/arrays for anything missing; never fabricate.
- Only call emit_profile, and output nothing else."""


def extract_text(source: Any) -> str:
    """Extract plain text from a PDF.

    `source` may be a path, bytes, or a file-like object (e.g. a Streamlit upload).
    A scanned PDF (no text layer) yields an empty string.
    """
    from pypdf import PdfReader

    if isinstance(source, (bytes, bytearray)):
        reader = PdfReader(io.BytesIO(source))
    elif hasattr(source, "read"):
        reader = PdfReader(source)
    else:
        reader = PdfReader(str(source))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()


def parse_profile(text: str, client: Optional[Any] = None) -> dict:
    """Extract resume text into a normalized profile dict.

    `client` defaults to the shared Groq client (needs GROQ_API_KEY).
    """
    raw = run_step_tool(
        role="a resume structuring extractor",
        task=EXTRACTION_TASK,
        expected_output="The complete candidate profile, emitted via emit_profile.",
        context=[text],
        tool=emit_profile_tool(),
        client=client,
        model=MODEL,
        max_tokens=8192,
    )
    profile = normalize_profile(raw)
    if not (profile["name"] or profile["skills"]["technical"] or profile["experience"]):
        raise ValueError("extraction produced an empty profile")
    profile["raw_text"] = text
    return profile
