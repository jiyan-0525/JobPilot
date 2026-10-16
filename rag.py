"""Minimal working RAG: load docs -> chunk -> embed -> retrieve.

Only two dependencies:
- fastembed: local embedding model (ONNX, no GPU / torch needed)
- numpy: store vectors + compute cosine similarity
"""
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-zh-v1.5"  # Chinese-optimized, 512-dim, small footprint
CHUNK_SIZE, CHUNK_OVERLAP = 400, 80    # chunking params (in characters)

# Similarity threshold: below this we treat it as "nothing relevant in the store".
# bge-zh scores are compressed (relevant ~0.45-0.7, irrelevant ~0.2-0.3), so 0.40.
MIN_SCORE = 0.40


def load_documents(folder="knowledge"):
    """Read every .md / .txt document under the folder."""
    return [
        {"source": str(path), "text": path.read_text(encoding="utf-8")}
        for path in sorted(Path(folder).rglob("*"))
        if path.is_file() and path.suffix in (".md", ".txt")
    ]


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Chunk by paragraph: split on paragraph boundaries first, and hard-split
    with overlap only when a single paragraph is too long."""
    chunks, current = [], ""
    for para in (p.strip() for p in text.split("\n\n") if p.strip()):
        if len(current) + len(para) + 2 <= size:  # still fits -> keep appending
            current = f"{current}\n\n{para}" if current else para
            continue
        if current:
            chunks.append(current)
        while len(para) > size:  # paragraph too long: hard-split with overlap
            chunks.append(para[:size])
            para = para[size - overlap:]
        current = para
    if current:
        chunks.append(current)
    return chunks


def _normalize(matrix):
    """L2-normalize along the last axis — after that, dot product == cosine similarity."""
    return matrix / np.linalg.norm(matrix, axis=-1, keepdims=True)


class KnowledgeBase:
    """In-memory vector store: embed every chunk, then retrieve by cosine similarity."""

    def __init__(self, folder="knowledge"):
        self.model = TextEmbedding(MODEL_NAME)
        # Collect every chunk and remember which file each came from
        self.chunks = [
            {"text": piece, "source": doc["source"]}
            for doc in load_documents(folder)
            for piece in chunk_text(doc["text"])
        ]
        if self.chunks:
            self.vectors = _normalize(
                np.array(list(self.model.embed([c["text"] for c in self.chunks])))
            )
        else:
            self.vectors = np.zeros((0, 1), dtype=np.float32)

    def search(self, query, k=3):
        """Return the k chunks most relevant to `query`, with score and source."""
        if not self.chunks:
            return []
        q = _normalize(np.array(list(self.model.embed([query]))[0], dtype=np.float32))
        scores = self.vectors @ q  # cosine similarity
        top = np.argsort(scores)[::-1][:k]
        return [
            {"score": float(scores[i]), "source": self.chunks[i]["source"],
             "text": self.chunks[i]["text"]}
            for i in top
            if float(scores[i]) >= MIN_SCORE
        ]
