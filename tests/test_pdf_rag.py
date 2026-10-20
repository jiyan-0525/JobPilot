"""Offline tests for the LangChain RAG PDF pipeline (pdf_rag.py).

No network, no GROQ_API_KEY: the vector store is built from a minimal
single-page PDF fixture and queried directly.
"""
import io

from langchain_core.documents import Document

from pdf_rag import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    _split_documents,
    build_vector_store,
    extract_profile_with_rag,
    query_pdf,
)
from tests.test_resume import VALID_PROFILE, FakeClient, _make_pdf


# ---- chunking --------------------------------------------------------------

def test_split_documents_splits_long_text_into_overlapping_chunks():
    long_text = " ".join(f"sentence {i}" for i in range(200))
    docs = [Document(page_content=long_text, metadata={"source": "fixture"})]
    chunks = _split_documents(docs)
    assert len(chunks) > 1
    assert all(0 < len(c.page_content) <= CHUNK_SIZE + CHUNK_OVERLAP for c in chunks)
    # overlap should make consecutive chunks share some words
    first_words = set(chunks[0].page_content.split())
    second_words = set(chunks[1].page_content.split())
    assert first_words & second_words


def test_split_documents_preserves_metadata():
    docs = [Document(page_content="hello world", metadata={"source": "a.md"})]
    chunks = _split_documents(docs)
    assert chunks[0].metadata["source"] == "a.md"


# ---- vector store -----------------------------------------------------------

def test_build_vector_store_and_query_pdf_returns_relevant_chunks():
    text = (
        "Anna Beispiel ist Data Engineerin in Stuttgart. "
        "Sie arbeitet mit Python, SQL und Docker. "
        "Bevor sie Data Engineerin wurde, studierte sie Informatik an der Uni Stuttgart."
    )
    store = build_vector_store(io.BytesIO(_make_pdf(text)))

    hits = query_pdf(store, "Welche Programmiersprachen beherrscht Anna?", k=1)
    assert len(hits) == 1
    assert "Python" in hits[0].page_content or "SQL" in hits[0].page_content


def test_build_vector_store_raises_on_empty_pdf():
    import pytest

    with pytest.raises(ValueError, match="No text extracted"):
        build_vector_store(io.BytesIO(_make_pdf("")))


def test_query_pdf_respects_k():
    text = " ".join(f"Zahl {i}" for i in range(300))
    store = build_vector_store(io.BytesIO(_make_pdf(text)))
    assert len(query_pdf(store, "Zahlen", k=2)) == 2


def test_embedding_model_is_chinese_optimized_bge():
    assert "bge" in EMBEDDING_MODEL


# ---- full pipeline ----------------------------------------------------------

def test_extract_profile_with_rag_returns_normalized_profile():
    text = (
        "Anna Beispiel, Data Engineerin in Stuttgart. "
        "Python, SQL und Docker. "
        "Studium der Informatik an der Uni Stuttgart."
    )
    client = FakeClient([VALID_PROFILE])
    profile = extract_profile_with_rag(io.BytesIO(_make_pdf(text)), client=client)

    assert profile["name"] == VALID_PROFILE["name"]
    assert profile["target_roles"] == VALID_PROFILE["target_roles"]
    # context must come from the retrieved chunks, not a raw dump
    context = client.last_request["messages"][1]["content"]
    assert "Anna Beispiel" in context
    assert profile["raw_text"]
