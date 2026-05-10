"""memory_engine.utils — 共享工具层（强制层）。

T-005 P0 + P1 实现：
- ``cache``         Hot Path 进程内 LRU + 5min TTL（cachetools.TTLCache）
- ``invariants``    W2 / W14 / W15 运行时 assert（DB CHECK 双保险）
- ``embeddings``    Doubao Embedding v1 包装（mock-first：sha256 派生 1024 维）
- ``llm_gateway``   Doubao 三档（heavy 2.0 / light 1.6）+ TPM 计数 + W12 降级
                    （mock-first：USE_LLM_MOCK=1 dev 默认；USE_LLM_MOCK=0 走真 httpx）

T-005 P2（待办）：
- ``feishu_client`` 飞书 API 调用唯一入口（W13 强制 trace_log INSERT）

详见 [docs/04-ENGUIDE.md §4 §5 §8.9](../../docs/04-ENGUIDE.md)。
"""

from memory_engine.utils.embeddings import (
    EMBEDDING_DIM,
    compute_embedding,
    cosine_similarity,
)
from memory_engine.utils.llm_gateway import (
    heavy_llm_extract,
    light_llm_extract,
)

__all__ = [
    "EMBEDDING_DIM",
    "compute_embedding",
    "cosine_similarity",
    "heavy_llm_extract",
    "light_llm_extract",
]
