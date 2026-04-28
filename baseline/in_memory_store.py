"""Baseline RAG 向量存储模块 - 纯内存版本"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


@dataclass
class TextChunk:
    """文本切片"""
    chunk_id: str
    content: str
    source_type: str
    source_id: Optional[str]
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    embedding: Optional[list[float]] = None


class InMemoryVectorStore:
    """纯内存向量存储（无需PostgreSQL）"""

    def __init__(self, embedding_dim: int = 1536):
        self.embedding_dim = embedding_dim
        self.chunks: list[TextChunk] = []

    def insert(self, chunk: TextChunk, embedding: list[float]) -> None:
        """插入切片"""
        chunk.embedding = embedding
        self.chunks.append(chunk)

    def batch_insert(self, chunks: list[TextChunk], embeddings: list[list[float]]) -> None:
        """批量插入"""
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
            self.chunks.append(chunk)

    def search(self, query_embedding: list[float], top_k: int = 5, source_filter: Optional[str] = None) -> list[dict]:
        """向量相似度检索（余弦相似度）"""
        if not self.chunks:
            return []

        query_vec = np.array(query_embedding)

        chunks_to_search = self.chunks
        if source_filter:
            chunks_to_search = [c for c in self.chunks if c.source_type == source_filter]

        if not chunks_to_search:
            return []

        results = []
        for chunk in chunks_to_search:
            if chunk.embedding is None:
                continue
            chunk_vec = np.array(chunk.embedding)
            similarity = float(np.dot(query_vec, chunk_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec) + 1e-10))
            results.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "metadata": chunk.metadata,
                "created_at": chunk.created_at,
                "similarity": similarity,
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def delete(self, chunk_id: str) -> None:
        """删除切片"""
        self.chunks = [c for c in self.chunks if c.chunk_id != chunk_id]

    def clear(self) -> None:
        """清空所有切片"""
        self.chunks = []

    def count(self) -> int:
        """统计切片数量"""
        return len(self.chunks)

    def get_all(self) -> list[TextChunk]:
        """获取所有切片"""
        return self.chunks.copy()