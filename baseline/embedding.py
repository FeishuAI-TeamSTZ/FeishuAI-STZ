"""Baseline RAG Embedding模块 - OpenAI text-embedding-3-small"""
from typing import Optional

import httpx

from .config import config


class EmbeddingModel:
    """OpenAI Embedding 模型封装"""

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or config.OPENAI_API_KEY
        self.model = model
        self.dimension = 1536
        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10.0,
        )

    def encode(self, texts: str | list[str]) -> list[list[float]]:
        """将文本转换为向量"""
        if isinstance(texts, str):
            texts = [texts]

        response = self._client.post(
            "/embeddings",
            json={
                "input": texts,
                "model": self.model,
                "dimensions": self.dimension,
            },
        )
        response.raise_for_status()
        data = response.json()

        return [item["embedding"] for item in data["data"]]

    def encode_single(self, text: str) -> list[float]:
        """将单个文本转换为向量"""
        return self.encode(texts=[text])[0]

    def close(self) -> None:
        """关闭HTTP客户端"""
        self._client.close()


embedding_model = EmbeddingModel()