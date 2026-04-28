"""Baseline RAG 文本分块模块"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Chunk:
    """文本块"""
    chunk_id: str
    content: str
    source_type: str
    source_id: Optional[str]
    metadata: dict
    created_at: datetime


class Chunker:
    """固定大小文本分块器"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str, source_type: str, source_id: Optional[str] = None, metadata: Optional[dict] = None) -> list[Chunk]:
        """将长文本切分为多个块"""
        if not text or not text.strip():
            return []

        text = text.strip()
        chunks = []

        if len(text) <= self.chunk_size:
            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                content=text,
                source_type=source_type,
                source_id=source_id,
                metadata=metadata or {},
                created_at=datetime.now(),
            ))
            return chunks

        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]

            if start > 0 and start + self.chunk_overlap < len(text):
                chunk_text = text[start - self.chunk_overlap:end]

            chunk_text = chunk_text.strip()
            if chunk_text:
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    content=chunk_text,
                    source_type=source_type,
                    source_id=source_id,
                    metadata=metadata or {},
                    created_at=datetime.now(),
                ))

            start += self.chunk_size

        return chunks

    def chunk_messages(self, messages: list[dict], source_type: str = "feishu_message") -> list[Chunk]:
        """将消息列表转换为块（每条消息一个块）"""
        chunks = []
        for msg in messages:
            msg_id = msg.get("id") or msg.get("message_id")
            content = msg.get("content") or msg.get("text", "")
            
            if content and content.strip():
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    content=content.strip(),
                    source_type=source_type,
                    source_id=msg_id,
                    metadata={
                        "sender": msg.get("sender"),
                        "timestamp": msg.get("timestamp") or msg.get("created_at"),
                    },
                    created_at=datetime.now(),
                ))
        return chunks

    def chunk_decisions(self, decisions: list[dict]) -> list[Chunk]:
        """将决策列表转换为块"""
        chunks = []
        for decision in decisions:
            decision_id = decision.get("id") or decision.get("decision_id")
            content = decision.get("content") or decision.get("text", "")
            
            if content and content.strip():
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    content=content.strip(),
                    source_type="decision",
                    source_id=decision_id,
                    metadata={
                        "subject": decision.get("subject"),
                        "predicate": decision.get("predicate"),
                        "object": decision.get("object"),
                        "provenance": decision.get("provenance"),
                    },
                    created_at=datetime.now(),
                ))
        return chunks