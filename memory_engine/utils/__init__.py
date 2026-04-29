"""memory_engine.utils — 共享工具层（强制层）。

- llm_gateway      LLM 调用唯一入口（CLAUDE.md §2.5 强制）
- feishu_client    飞书 API 调用唯一入口（W13 强制）
- cache            Hot Path LRU + 5min TTL
- embeddings       Doubao Embedding v1 包装
- invariants       W1–W15 运行时检查

详见 docs/04-ENGUIDE.md §8.9。

T-001 占位；T-004 实现真接口。
"""
