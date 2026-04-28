"""Baseline RAG 配置"""
import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Config:
    """Baseline RAG 配置（固定不变）"""

    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    TOP_K: int = 5

    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 500

    DB_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    DB_NAME: str = os.getenv("POSTGRES_DB", "baseline_rag")
    DB_USER: str = os.getenv("POSTGRES_USER", "postgres")
    DB_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


config = Config()