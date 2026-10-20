"""LangChain + RAG for PDF reading.

Replaces the direct pypdf extraction with a LangChain pipeline:
PDF -> PyPDFLoader -> RecursiveCharacterTextSplitter -> FastEmbed embeddings -> FAISS vector store

The vector store is built once per PDF and can be queried for relevant chunks.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any, Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80


def _load_pdf(source: Any) -> list[Document]:
    """Load a PDF into LangChain Documents using PyPDFLoader.

    `source` may be a path, bytes, or a file-like object (e.g. a Streamlit upload).
    Documents with no text layer (e.g. scans) are dropped.
    """
    if isinstance(source, (bytes, bytearray)):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(source)
            f.flush()
            loader = PyPDFLoader(f.name)
            docs = loader.load()
            Path(f.name).unlink(missing_ok=True)
            return _drop_empty(docs)
    elif hasattr(source, "read"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(source.read())
            f.flush()
            loader = PyPDFLoader(f.name)
            docs = loader.load()
            Path(f.name).unlink(missing_ok=True)
            return _drop_empty(docs)
    else:
        loader = PyPDFLoader(str(source))
        return _drop_empty(loader.load())


def _drop_empty(docs: list[Document]) -> list[Document]:
    """Keep only documents that actually carry a text layer."""
    return [d for d in docs if (d.page_content or "").strip()]


def _split_documents(docs: list[Document]) -> list[Document]:
    """Split documents into chunks using RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


def build_vector_store(source: Any) -> FAISS:
    """Build a FAISS vector store from a PDF source.

    Returns the vector store, which can be queried with `.similarity_search()`.
    """
    docs = _load_pdf(source)
    if not docs:
        raise ValueError("No text extracted — likely a scanned PDF (OCR unsupported).")

    chunks = _split_documents(docs)
    embeddings = FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)
    return FAISS.from_documents(chunks, embeddings)


def query_pdf(vector_store: FAISS, query: str, k: int = 3) -> list[Document]:
    """Query the vector store for relevant chunks."""
    return vector_store.similarity_search(query, k=k)


def extract_profile_with_rag(source: Any, client: Optional[Any] = None) -> dict:
    """Extract a structured profile from a PDF using LangChain RAG.

    Builds a vector store from the PDF, retrieves relevant chunks for profile
    extraction, and sends them to the LLM.
    """
    from resume_jobs.schema import emit_profile_tool, normalize_profile
    from resume_jobs.step import run_step_tool
    from resume_jobs.llm import get_model

    docs = _load_pdf(source)
    if not docs:
        raise ValueError("No text extracted — likely a scanned PDF (OCR unsupported).")

    chunks = _split_documents(docs)
    embeddings = FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)
    vector_store = FAISS.from_documents(chunks, embeddings)

    query = "Extract the complete candidate profile including name, contact, skills, experience, education, languages, target roles, career level, and summary."
    relevant_chunks = vector_store.similarity_search(query, k=5)
    context = [chunk.page_content for chunk in relevant_chunks]

    raw = run_step_tool(
        role="a resume structuring extractor",
        task="Extract the resume into the structured profile. Use the provided context chunks from the resume.",
        expected_output="The complete candidate profile, emitted via emit_profile.",
        context=context,
        tool=emit_profile_tool(),
        client=client,
        model=get_model(),
        max_tokens=8192,
    )
    profile = normalize_profile(raw)
    if not (profile["name"] or profile["skills"]["technical"] or profile["experience"]):
        raise ValueError("extraction produced an empty profile")
    profile["raw_text"] = "\n\n".join(chunk.page_content for chunk in chunks)
    return profile
