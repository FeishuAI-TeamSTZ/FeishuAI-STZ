"""initial schema (op.execute schema.sql 整文件包装).

Revision ID: 0001
Revises:
Create Date: 2026-05-05

T-004 D22：alembic 0001 = `op.execute(schema.sql)` 整文件包装；schema.sql 是单一真相源
（CLAUDE.md §2.4），v1 周期内不会有破坏性 schema 改动；alembic 真正派上用场是 v2 字段演进。
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op

# alembic 版本元数据 ---------------------------------------------------------
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

# schema.sql 路径（项目根；migrations/versions/ 上溯两级）
SCHEMA_SQL_PATH = Path(__file__).resolve().parents[2] / "schema.sql"


def upgrade() -> None:
    """灌入完整 schema.sql（6 enums + 8 主表 + 索引 + CHECK + 触发器）。"""
    sql_text = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    op.execute(sa.text(sql_text))


def downgrade() -> None:
    """反向 DROP 全部对象（不 DROP EXTENSION vector，其他 schema 可能依赖）。"""
    # 表（CASCADE 解 FK 依赖；按 FK 倒序）
    op.execute(
        "DROP TABLE IF EXISTS "
        "decay_calculations, reflect_logs, cards, card_quota, "
        "decision_embeddings, decisions, trace_log, users CASCADE"
    )
    # 6 个 enum 类型（按字母序，依赖关系无所谓）
    op.execute(
        "DROP TYPE IF EXISTS "
        "card_response_enum, card_status_enum, card_type_enum, "
        "decision_state_enum, evolution_type_enum, provenance_enum"
    )
    # 触发器函数
    op.execute("DROP FUNCTION IF EXISTS update_updated_at()")
