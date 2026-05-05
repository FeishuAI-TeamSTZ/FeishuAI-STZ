"""集成测：testcontainers PG → alembic upgrade → schema 一致性 + W2/W14 反向。

T-004 D23：默认通过 `pyproject.toml addopts -m "not integration"` 跳过；
显式 `pytest -m integration` 才跑。

T-004 D22 验证链：
1. 起 PG 容器（pgvector/pgvector:pg16，与 docker-compose 同镜像，本地已缓存）
2. `alembic upgrade head` 灌入 schema.sql
3. `validate_consistency.check()` 直接调用（避免 subprocess + uv 依赖问题）
4. 反向插入 W2 / W14 违规记录 → 期望 IntegrityError
"""

from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from testcontainers.postgres import PostgresContainer

from scripts.validate_consistency import check

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.integration


# ============================================================
# Fixture：testcontainers PG + alembic upgrade
# ============================================================


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    """起 PG 容器 → alembic upgrade head → 返 engine（module 级复用）。"""
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as pg:
        url = pg.get_connection_url()
        env = {**os.environ, "DATABASE_URL": url}
        # alembic CLI 必走 subprocess（无 import API 等价路径）
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=str(ROOT),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        yield create_engine(url)


# ============================================================
# 测试用例（5 个）
# ============================================================


def test_validate_consistency_zero_after_upgrade(pg_engine: Engine) -> None:
    """alembic upgrade 后 validate_consistency.check() 应返回空漂移列表。"""
    drifts = check()
    assert drifts == [], f"schema.sql ↔ ORM 漂移:\n" + "\n".join(drifts)


def test_pgvector_extension_loaded(pg_engine: Engine) -> None:
    """pgvector 扩展 0.8.x 装好（schema.sql 头部 CREATE EXTENSION）。"""
    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
    assert row is not None, "pgvector 扩展未装"
    assert row[0] == "vector"
    assert row[1].startswith("0.8"), f"期望 pgvector 0.8.x，得到 {row[1]}"


def test_w2_check_neg_supersedes_null_parent(pg_engine: Engine) -> None:
    """W2 CHECK 负样本：SUPERSEDES + parent_id NULL → IntegrityError。"""
    with pytest.raises(IntegrityError, match="chk_decisions_evolution_parent"):
        with pg_engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO decisions (
                        subject, predicate, object, logical_timestamp,
                        provenance, confidence, evolution_type
                    ) VALUES (
                        '测试', 'TEST', 'value', now(),
                        'USER_STATED', 0.9, 'SUPERSEDES'
                    )
                """)
            )


def test_w2_check_pos_root_no_parent(pg_engine: Engine) -> None:
    """W2 CHECK 正样本：ROOT + parent_id NULL → 成功 + 默认值。"""
    with pg_engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO decisions (
                    subject, predicate, object, logical_timestamp,
                    provenance, confidence, evolution_type
                ) VALUES (
                    '项目X', 'RELEASE_DATE', '2026-05-15', now(),
                    'USER_STATED', 0.95, 'ROOT'
                )
                RETURNING decision_id, state, evolution_type, confidence
            """)
        ).fetchone()
    assert row is not None
    assert isinstance(row[0], uuid.UUID)
    assert row[1] == "ACTIVE"  # state default
    assert row[2] == "ROOT"
    assert float(row[3]) == 0.95


def test_w14_check_neg_count_exceeds_max(pg_engine: Engine) -> None:
    """W14 CHECK 负样本：count > max_daily → IntegrityError。"""
    test_user = f"u_{uuid.uuid4().hex[:8]}"
    with pg_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (user_id, name) VALUES (:u, :n)"),
            {"u": test_user, "n": "test"},
        )
    with pytest.raises(IntegrityError, match="chk_card_quota_count"):
        with pg_engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO card_quota (user_id, quota_date, count, max_daily)
                    VALUES (:u, '2026-04-29', 6, 5)
                """),
                {"u": test_user},
            )
