"""Resume parsing (Resume -> Profile JSON) minimal module.

Step 1 does only: upload PDF -> extract text -> LLM structuring -> profile dict.
No network (except the LLM), no job API, no RAG.
"""

from resume_jobs.resume import extract_text, parse_profile

__all__ = ["extract_text", "parse_profile"]
