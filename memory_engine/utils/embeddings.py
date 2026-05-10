"""Doubao Embedding v1 包装（1024 维）+ 余弦相似度。

T-005 P1 D26：mock-first
- ``USE_LLM_MOCK=1``（dev 默认）：``hashlib.sha256`` 派生 deterministic 1024 浮点向量
- ``USE_LLM_MOCK=0``（prod）：httpx POST 到 Doubao Embedding EP

签名对齐 [04-ENGUIDE §8.9](../docs/04-ENGUIDE.md)：
- ``compute_embedding(text) -> list[float]``  长度 1024
- ``cosine_similarity(a, b) -> float``  ∈ [-1, 1]
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Any, cast

import httpx

from memory_engine.config import get_settings
from memory_engine.exceptions import LLMResponseInvalidError, LLMTimeoutError

EMBEDDING_DIM = 1024  # Doubao Embedding v1 默认维度（与 03-SCHEMA §3.8 锁定）


def _is_mock_mode() -> bool:
    """读 env var：``USE_LLM_MOCK`` 默认开（"1"）；显式设 "0" 才走真路径。"""
    return os.environ.get("USE_LLM_MOCK", "1") != "0"


# ---------------------------------------------------------------- Mock impl

def _mock_embedding(text: str) -> list[float]:
    """deterministic 1024 维向量：sha256 反复哈希 + bytes → 浮点 + 单位归一化。

    保证：
    - 同样 text 产出同样向量（单测可重复）
    - 不同 text 产出不同向量（碰撞概率 ≈ 2⁻²⁵⁶）
    - 输出归一化为单位向量（cosine 内积即余弦）
    """
    vec: list[float] = []
    seed = text.encode("utf-8")
    while len(vec) < EMBEDDING_DIM:
        h = hashlib.sha256(seed).digest()  # 32 字节
        for byte in h:
            vec.append((byte - 127.5) / 127.5)  # 映射到 [-1, 1]
        seed = h  # rehash 拿更多字节
    vec = vec[:EMBEDDING_DIM]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


# ---------------------------------------------------------------- Real impl

def _real_embedding(text: str) -> list[float]:
    """真调 Doubao Embedding v1（httpx 同步）；lazy load Settings（mock 模式不触发）。"""
    settings = get_settings()
    if not settings.doubao_embedding_endpoint_id:
        raise LLMResponseInvalidError(
            extra={"reason": "DOUBAO_EMBEDDING_ENDPOINT_ID 未配置"}
        )
    try:
        response = httpx.post(
            f"{settings.doubao_base_url}/embeddings",
            headers={"Authorization": f"Bearer {settings.doubao_api_key}"},
            json={
                "model": settings.doubao_embedding_endpoint_id,
                "input": [text],
            },
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(extra={"category": "EMBEDDING", "text_len": len(text)}) from e
    except httpx.HTTPError as e:
        raise LLMResponseInvalidError(extra={"reason": str(e)}) from e

    try:
        data = cast(dict[str, Any], response.json())
        embedding = cast(list[float], data["data"][0]["embedding"])
    except (KeyError, IndexError, ValueError) as e:
        raise LLMResponseInvalidError(extra={"reason": f"解析 Doubao 响应失败：{e}"}) from e

    if len(embedding) != EMBEDDING_DIM:
        raise LLMResponseInvalidError(
            extra={"reason": f"Doubao 返回 {len(embedding)} 维，期望 {EMBEDDING_DIM}"}
        )
    return embedding


# ---------------------------------------------------------------- 公开 API

def compute_embedding(text: str) -> list[float]:
    """计算文本嵌入；mock / real 由 ``USE_LLM_MOCK`` env 切换。"""
    if not text:
        raise ValueError("text 不能为空")
    return _mock_embedding(text) if _is_mock_mode() else _real_embedding(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度 ∈ [-1, 1]；零向量返 0。"""
    if len(a) != len(b):
        raise ValueError(f"维度不一致：len(a)={len(a)}, len(b)={len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


__all__ = [
    "EMBEDDING_DIM",
    "compute_embedding",
    "cosine_similarity",
]
