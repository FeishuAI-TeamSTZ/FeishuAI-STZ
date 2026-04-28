"""Baseline RAG 主入口"""
from typing import Optional

from .chunker import Chunker
from .config import config
from .embedding import EmbeddingModel, embedding_model
from .retriever import Retriever
from .in_memory_store import InMemoryVectorStore


class BaselineRAG:
    """Baseline RAG 主类"""

    SYSTEM_PROMPT = """你是一个智能助手，基于提供的上下文信息回答用户问题。
如果上下文中没有相关信息，请明确告知用户。

注意：
- 只基于提供的上下文回答，不要编造信息
- 如果多条上下文信息矛盾，选择最相关的
- 回答要清晰、简洁
"""

    def __init__(
        self,
        use_memory: bool = True,
        chunker: Optional[Chunker] = None,
        embedding: Optional[EmbeddingModel] = None,
    ):
        if use_memory:
            self.vector_store = InMemoryVectorStore()
        else:
            from .vector_store import VectorStore
            self.vector_store = VectorStore()
        
        self.chunker = chunker or Chunker()
        self.embedding = embedding or embedding_model
        self.retriever = Retriever(self.vector_store, self.embedding)
        self._client = None
        if config.OPENAI_API_KEY:
            import httpx
            self._client = httpx.Client(
                base_url="https://api.openai.com/v1",
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                timeout=30.0,
            )

    def add_text(self, text: str, source_type: str = "text", source_id: Optional[str] = None, metadata: Optional[dict] = None) -> int:
        """添加文本到知识库，返回添加的块数量"""
        chunks = self.chunker.chunk_text(text, source_type, source_id, metadata)
        if chunks:
            self.retriever.add_chunks(chunks)
        return len(chunks)

    def add_messages(self, messages: list) -> int:
        """批量添加飞书消息"""
        chunks = self.chunker.chunk_messages(messages)
        if chunks:
            self.retriever.add_chunks(chunks)
        return len(chunks)

    def add_decisions(self, decisions: list) -> int:
        """批量添加决策"""
        chunks = self.chunker.chunk_decisions(decisions)
        if chunks:
            self.retriever.add_chunks(chunks)
        return len(chunks)

    def query(self, question: str, top_k: int = 5) -> dict:
        """查询并返回回答"""
        context = self.retriever.search_with_context(question, top_k)
        
        if not context:
            return {
                "question": question,
                "answer": "抱歉，知识库中没有找到相关信息。",
                "sources": [],
                "context_used": False,
            }

        if not self._client:
            return {
                "question": question,
                "answer": "请配置OPENAI_API_KEY以获取LLM回答",
                "sources": self.retriever.search(question, top_k),
                "context_used": True,
            }

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"上下文信息：\n{context}\n\n问题：{question}"},
        ]

        response = self._client.post(
            "/chat/completions",
            json={
                "model": config.LLM_MODEL,
                "messages": messages,
                "temperature": config.LLM_TEMPERATURE,
                "max_tokens": config.LLM_MAX_TOKENS,
            },
        )
        response.raise_for_status()
        data = response.json()
        
        answer = data["choices"][0]["message"]["content"]

        sources = self.retriever.search(question, top_k)
        
        return {
            "question": question,
            "answer": answer,
            "sources": [{"content": s["content"], "similarity": s["similarity"]} for s in sources],
            "context_used": True,
            "context_chunks": len(sources),
        }

    def query_without_llm(self, question: str, top_k: int = 5) -> dict:
        """查询但不做LLM生成，只返回检索结果（用于测试）"""
        sources = self.retriever.search(question, top_k)
        return {
            "question": question,
            "answer": None,
            "sources": [{"content": s["content"], "similarity": s["similarity"]} for s in sources],
            "context_used": len(sources) > 0,
        }

    def clear(self) -> None:
        """清空知识库"""
        self.retriever.clear()

    def count(self) -> int:
        """返回知识库中的块数量"""
        return self.retriever.count()

    def close(self) -> None:
        """关闭客户端"""
        if self._client:
            self._client.close()

    def __enter__(self) -> "BaselineRAG":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()