"""Resume parsing (Resume -> Profile JSON) minimal module.

Step 1 does only: upload PDF -> extract text -> LLM structuring -> profile dict.
No network (except the LLM), no job API, no RAG.
"""

from resume_jobs.resume import extract_text, parse_profile
from pdf_rag import build_vector_store, query_pdf, extract_profile_with_rag

__all__ = ["extract_text", "parse_profile", "build_vector_store", "query_pdf", "extract_profile_with_rag"]
