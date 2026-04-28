"""Baseline RAG 检索模块"""
from typing import Optional, List

from .chunker import Chunk


class Retriever:
    """向量检索器"""

    def __init__(
        self,
        vector_store,
        embedding,
    ):
        self.vector_store = vector_store
        self.embedding = embedding

    def add_chunk(self, chunk: Chunk) -> None:
        """添加单个块"""
        embedding = self.embedding.encode_single(chunk.content)
        self.vector_store.insert(chunk, embedding)

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """批量添加块"""
        if not chunks:
            return
        contents = [c.content for c in chunks]
        embeddings = self.embedding.encode(contents)
        self.vector_store.batch_insert(chunks, embeddings)

    def search(self, query: str, top_k: int = 5, source_filter: Optional[str] = None) -> List[dict]:
        """检索相关内容"""
        query_embedding = self.embedding.encode_single(query)
        results = self.vector_store.search(query_embedding, top_k, source_filter)
        return results

    def search_with_context(self, query: str, top_k: int = 5) -> str:
        """检索并拼接为上下文字符串"""
        results = self.search(query, top_k)
        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[来源{i}]: {result['content']}")
        
        return "\n\n".join(context_parts)

    def clear(self) -> None:
        """清空向量库"""
        self.vector_store.clear()

    def count(self) -> int:
        """统计向量库中的块数量"""
        return self.vector_store.count()