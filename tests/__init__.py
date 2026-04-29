"""tests — 单元 + 集成测试（不含 benchmark）。

- tests/unit/         纯单元（mock 全部 I/O）
- tests/integration/  集成测（testcontainers PG，mock LLM/Feishu）
- tests/fixtures/     共享 fixture 数据（与 benchmark/fixtures/ 分离）

详见 docs/04-ENGUIDE.md §6。
"""
