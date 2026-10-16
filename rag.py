"""最小可用 RAG：加载文档 → 切块 → 向量化 → 检索

只用两个依赖：
- fastembed：本地 embedding 模型（ONNX，无需 GPU / torch）
- numpy：存向量 + 算余弦相似度

跑法：
    .venv/bin/python rag.py
"""
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-zh-v1.5"  # 中文优化、512 维、体积小
CHUNK_SIZE, CHUNK_OVERLAP = 400, 80    # 切块参数（按字符数）

# 相似度阈值：低于它就认为"库里没有相关内容"
# bge-zh 的分数偏"压缩"（相关约 0.45~0.7，无关约 0.2~0.3），所以阈值取 0.40
MIN_SCORE = 0.40


def load_documents(folder="knowledge"):
    """读取文件夹下所有 .md / .txt 文档。"""
    return [
        {"source": str(path), "text": path.read_text(encoding="utf-8")}
        for path in sorted(Path(folder).rglob("*"))
        if path.is_file() and path.suffix in (".md", ".txt")
    ]


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """按段落切块：优先在段落边界切，单段过长时再按字符硬切并保留重叠。"""
    chunks, current = [], ""
    for para in (p.strip() for p in text.split("\n\n") if p.strip()):
        if len(current) + len(para) + 2 <= size:  # 还能塞进当前块就继续拼
            current = f"{current}\n\n{para}" if current else para
            continue
        if current:
            chunks.append(current)
        while len(para) > size:  # 单段过长：硬切并保留 overlap
            chunks.append(para[:size])
            para = para[size - overlap:]
        current = para
    if current:
        chunks.append(current)
    return chunks


def _normalize(matrix):
    """按最后一维做 L2 归一化 —— 归一化后点积就等于余弦相似度。"""
    return matrix / np.linalg.norm(matrix, axis=-1, keepdims=True)


class KnowledgeBase:
    """内存版向量库：把所有片段向量化后，用余弦相似度做检索。"""

    def __init__(self, folder="knowledge"):
        self.model = TextEmbedding(MODEL_NAME)
        # 收集所有片段，并记住每段来自哪个文件
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
        """返回与 query 最相关的 k 个片段，含相似度和来源。"""
        if not self.chunks:
            return []
        q = _normalize(np.array(list(self.model.embed([query]))[0], dtype=np.float32))
        scores = self.vectors @ q  # 余弦相似度
        top = np.argsort(scores)[::-1][:k]
        return [
            {"score": float(scores[i]), "source": self.chunks[i]["source"],
             "text": self.chunks[i]["text"]}
            for i in top
            if float(scores[i]) >= MIN_SCORE
        ]


if __name__ == "__main__":
    kb = KnowledgeBase()
    print(f"已索引 {len(kb.chunks)} 个片段\n")

    for question in [
        "什么是 RAG？",
        "现在用的是什么模型？",
        "天气数据是从哪来的？",
        "agent 是怎么调用工具的？",
        "今天午饭吃什么？",
    ]:
        print(f"❓ {question}")
        hits = kb.search(question, k=2)
        if not hits:
            print("   （没有找到相关内容）")
        for hit in hits:
            snippet = hit["text"].replace("\n", " ")[:70]
            print(f"   [{hit['score']:.3f}] {hit['source']}: {snippet}...")
        print()
