"""最小可用 RAG：加载文档 → 切块 → 向量化 → 检索

只用两个依赖：
- fastembed：本地 embedding 模型（ONNX，无需 GPU / torch）
- numpy：存向量 + 算余弦相似度

跑法：
    .venv/bin/python rag.py
"""
import glob
import os

import numpy as np
from fastembed import TextEmbedding

# 本地 embedding 模型：中文优化、512 维、体积小
MODEL_NAME = "BAAI/bge-small-zh-v1.5"

# 切块参数（按字符数）
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80

# 相似度阈值：低于它就认为"库里没有相关内容"
# bge-zh 的分数偏"压缩"（相关约 0.45~0.7，无关约 0.2~0.3），所以阈值取 0.40
MIN_SCORE = 0.40


def load_documents(folder="knowledge"):
    """读取文件夹下所有 .md / .txt 文档。"""
    docs = []
    pattern = os.path.join(folder, "**", "*")
    for path in sorted(glob.glob(pattern, recursive=True)):
        if os.path.isfile(path) and path.endswith((".md", ".txt")):
            with open(path, encoding="utf-8") as f:
                docs.append({"source": path, "text": f.read()})
    return docs


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """按段落切块：优先在段落边界切，单段过长时再按字符硬切并保留重叠。"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""
    for para in paragraphs:
        # 还能塞进当前块就继续拼
        if len(current) + len(para) + 2 <= size:
            current = f"{current}\n\n{para}" if current else para
            continue

        if current:
            chunks.append(current)

        # 单段比 size 还长，硬切，并让相邻块有 overlap 的重叠
        while len(para) > size:
            chunks.append(para[:size])
            para = para[size - overlap:]

        current = para

    if current:
        chunks.append(current)

    return chunks


class KnowledgeBase:
    """内存版向量库：把所有片段向量化后，用余弦相似度做检索。"""

    def __init__(self, folder="knowledge"):
        self.model = TextEmbedding(MODEL_NAME)

        # 收集所有片段，并记住每段来自哪个文件
        self.chunks = []
        for doc in load_documents(folder):
            for piece in chunk_text(doc["text"]):
                self.chunks.append({"text": piece, "source": doc["source"]})

        if not self.chunks:
            self.vectors = np.zeros((0, 1), dtype=np.float32)
            return

        # 向量化，并做 L2 归一化 —— 归一化后点积就等于余弦相似度
        raw = np.array(list(self.model.embed([c["text"] for c in self.chunks])))
        self.vectors = raw / np.linalg.norm(raw, axis=1, keepdims=True)

    def search(self, query, k=3):
        """返回与 query 最相关的 k 个片段，含相似度和来源。"""
        if not self.chunks:
            return []

        q = np.array(list(self.model.embed([query]))[0], dtype=np.float32)
        q = q / np.linalg.norm(q)

        scores = self.vectors @ q  # 余弦相似度
        top = np.argsort(scores)[::-1][:k]

        return [
            {
                "score": float(scores[i]),
                "source": self.chunks[i]["source"],
                "text": self.chunks[i]["text"],
            }
            for i in top
            if float(scores[i]) >= MIN_SCORE
        ]


if __name__ == "__main__":
    kb = KnowledgeBase()
    print(f"已索引 {len(kb.chunks)} 个片段\n")

    questions = [
        "什么是 RAG？",
        "现在用的是什么模型？",
        "天气数据是从哪来的？",
        "agent 是怎么调用工具的？",
        "今天午饭吃什么？",
    ]

    for question in questions:
        print(f"❓ {question}")
        hits = kb.search(question, k=2)
        if not hits:
            print("   （没有找到相关内容）")
        for hit in hits:
            snippet = hit["text"].replace("\n", " ")[:70]
            print(f"   [{hit['score']:.3f}] {hit['source']}: {snippet}...")
        print()
