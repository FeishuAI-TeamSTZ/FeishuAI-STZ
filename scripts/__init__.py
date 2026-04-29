"""scripts — 运维脚本（不包含业务逻辑）。

计划脚本：
    invariant_check.py        W2 / W4 等不变量巡检（每 1 min）
    validate_consistency.py   schema.sql ↔ models.py 漂移检查（pre-commit hook）
    seed_fixtures.py          演示种子数据灌注

详见 docs/04-ENGUIDE.md §1。
"""
