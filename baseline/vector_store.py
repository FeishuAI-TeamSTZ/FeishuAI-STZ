"""Baseline RAG 向量存储模块 - 基于 pgvector"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import config


@dataclass
class TextChunk:
    """文本切片"""
    chunk_id: str
    content: str
    source_type: str
    source_id: Optional[str]
    metadata: dict
    created_at: datetime


class VectorStore:
    """基于 pgvector 的向量存储"""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or config.database_url
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._init_schema()

    def _init_schema(self) -> None:
        """初始化数据库schema"""
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS text_chunks (
                    chunk_id VARCHAR(64) PRIMARY KEY,
                    content TEXT NOT NULL,
                    source_type VARCHAR(32) NOT NULL,
                    source_id VARCHAR(128),
                    metadata JSONB DEFAULT '{}',
                    embedding VECTOR(1536),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON text_chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_source
                ON text_chunks (source_type, source_id)
            """))
            conn.commit()

    def insert(self, chunk: TextChunk, embedding: list[float]) -> None:
        """插入切片"""
        with self.SessionLocal() as session:
            session.execute(
                text("""
                    INSERT INTO text_chunks (chunk_id, content, source_type, source_id, metadata, embedding, created_at)
                    VALUES (:chunk_id, :content, :source_type, :source_id, :metadata, :embedding::vector, :created_at)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding
                """),
                {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "source_type": chunk.source_type,
                    "source_id": chunk.source_id,
                    "metadata": chunk.metadata,
                    "embedding": embedding,
                    "created_at": chunk.created_at,
                }
            )
            session.commit()

    def batch_insert(self, chunks: list[TextChunk], embeddings: list[list[float]]) -> None:
        """批量插入"""
        with self.SessionLocal() as session:
            for chunk, embedding in zip(chunks, embeddings):
                session.execute(
                    text("""
                        INSERT INTO text_chunks (chunk_id, content, source_type, source_id, metadata, embedding, created_at)
                        VALUES (:chunk_id, :content, :source_type, :source_id, :metadata, :embedding::vector, :created_at)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            embedding = EXCLUDED.embedding
                    """),
                    {
                        "chunk_id": chunk.chunk_id,
                        "content": chunk.content,
                        "source_type": chunk.source_type,
                        "source_id": chunk.source_id,
                        "metadata": chunk.metadata,
                        "embedding": embedding,
                        "created_at": chunk.created_at,
                    }
                )
            session.commit()

    def search(self, query_embedding: list[float], top_k: int = 5, source_filter: Optional[str] = None) -> list[dict]:
        """向量相似度检索"""
        with self.SessionLocal() as session:
            if source_filter:
                result = session.execute(
                    text("""
                        SELECT chunk_id, content, source_type, source_id, metadata, created_at,
                               1 - (embedding <=> :query_embedding::vector) as similarity
                        FROM text_chunks
                        WHERE source_type = :source_type
                        ORDER BY embedding <=> :query_embedding::vector
                        LIMIT :top_k
                    """),
                    {"query_embedding": query_embedding, "source_type": source_filter, "top_k": top_k}
                )
            else:
                result = session.execute(
                    text("""
                        SELECT chunk_id, content, source_type, source_id, metadata, created_at,
                               1 - (embedding <=> :query_embedding::vector) as similarity
                        FROM text_chunks
                        ORDER BY embedding <=> :query_embedding::vector
                        LIMIT :top_k
                    """),
                    {"query_embedding": query_embedding, "top_k": top_k}
                )
            return [dict(row._mapping) for row in result]

    def delete(self, chunk_id: str) -> None:
        """删除切片"""
        with self.SessionLocal() as session:
            session.execute(text("DELETE FROM text_chunks WHERE chunk_id = :chunk_id"), {"chunk_id": chunk_id})
            session.commit()

    def clear(self) -> None:
        """清空所有切片"""
        with self.SessionLocal() as session:
            session.execute(text("TRUNCATE TABLE text_chunks"))
            session.commit()

    def count(self) -> int:
        """统计切片数量"""
        with self.SessionLocal() as session:
            result = session.execute(text("SELECT COUNT(*) FROM text_chunks"))
            return result.scalar()