"""ORM 层冒烟测试。

只校验：
- 8 张表可被 Base.metadata 发现
- 每个 Model 类可 instantiate（不连真 PG）
- 关键 CHECK 约束（W2 / W14 / W13）在 ``__table_args__`` 中存在
- 自引用 ``DecisionModel.parent`` relationship 解析正确

真 PG 端到端校验（INSERT 触发 CHECK 违反等）留 T-004 用 testcontainers。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table

from memory_engine.models import (
    Base,
    CardModel,
    CardQuotaModel,
    CardStatus,
    CardType,
    DecayCalculationModel,
    DecisionEmbeddingModel,
    DecisionModel,
    DecisionState,
    EvolutionType,
    Provenance,
    ReflectLogModel,
    TraceLogModel,
    UserModel,
)


def test_metadata_has_eight_tables() -> None:
    """schema.sql 8 张表均已在 Base.metadata 注册。"""
    expected = {
        "users",
        "trace_log",
        "decisions",
        "decision_embeddings",
        "card_quota",
        "cards",
        "reflect_logs",
        "decay_calculations",
    }
    assert set(Base.metadata.tables.keys()) == expected


@pytest.mark.parametrize(
    "model_cls",
    [
        UserModel,
        TraceLogModel,
        DecisionModel,
        DecisionEmbeddingModel,
        CardQuotaModel,
        CardModel,
        ReflectLogModel,
        DecayCalculationModel,
    ],
)
def test_model_class_can_instantiate_empty(model_cls: type) -> None:
    """每个 Model 类可空 instantiate（不写库）。"""
    instance = model_cls()
    assert instance is not None
    assert hasattr(instance, "__tablename__")


def test_decision_w2_check_present() -> None:
    """W2: ``chk_decisions_evolution_parent`` 存在于 decisions 表。"""
    constraints = [c.name for c in DecisionModel.__table_args__ if isinstance(c, CheckConstraint)]
    assert "chk_decisions_evolution_parent" in constraints


def test_card_quota_w14_check_present() -> None:
    """W14: ``chk_card_quota_count`` 存在于 card_quota 表。"""
    constraints = [c.name for c in CardQuotaModel.__table_args__ if isinstance(c, CheckConstraint)]
    assert "chk_card_quota_count" in constraints


def test_trace_log_w13_pk_not_null() -> None:
    """W13: ``trace_log.trace_id`` 是 PK 且非空。"""
    table = cast(Table, TraceLogModel.__table__)
    pk_cols = [c.name for c in table.primary_key.columns]
    assert pk_cols == ["trace_id"]
    trace_id_col = table.c.trace_id
    assert trace_id_col.nullable is False


def test_decision_self_referential_parent() -> None:
    """``DecisionModel.parent`` 自引用 relationship 指向自身。"""
    rel = DecisionModel.parent
    assert rel.property.mapper.class_ is DecisionModel


def test_decision_instantiate_with_root_fields() -> None:
    """ROOT 决策的最小字段集合可以构造（不连库）。"""
    d = DecisionModel(
        decision_id=uuid.uuid4(),
        subject="项目A",
        predicate="RELEASE_DATE",
        object="2026-05-15",
        logical_timestamp=datetime.now(tz=UTC),
        provenance=Provenance.USER_STATED,
        confidence=Decimal("0.95"),
        evolution_type=EvolutionType.ROOT,
    )
    assert d.subject == "项目A"
    assert d.evolution_type is EvolutionType.ROOT
    assert d.parent_id is None


def test_card_quota_default_max_daily_is_five() -> None:
    """W14 默认上限 5（来自 schema.sql server_default）。"""
    col = cast(Table, CardQuotaModel.__table__).c.max_daily
    server_default = col.server_default
    assert server_default is not None
    # server_default 是 TextClause，其 .arg 是 SQL 文本
    assert "5" in str(server_default.arg)  # type: ignore[attr-defined]


def test_card_model_dedup_index_exists() -> None:
    """W11 24h 去重索引（``idx_cards_dedup``）存在。"""
    indexes = {idx.name for idx in cast(Table, CardModel.__table__).indexes}
    assert "idx_cards_dedup" in indexes


def test_card_status_enum_values() -> None:
    """CardStatus 4 值（QUEUED / PUSHED / RESPONDED / EXPIRED）。"""
    assert {s.value for s in CardStatus} == {"QUEUED", "PUSHED", "RESPONDED", "EXPIRED"}


def test_card_type_enum_five_values() -> None:
    """CardType 5 值（HARD/SOFT/GHOST/CROSS_SYSTEM/EVOLUTION）。"""
    assert len(list(CardType)) == 5


def test_decision_state_five_values() -> None:
    """DecisionState 5 态（ACTIVE/STALE/HYPOTHESIS/GHOST/ARCHIVED）。"""
    assert {s.value for s in DecisionState} == {
        "ACTIVE",
        "STALE",
        "HYPOTHESIS",
        "GHOST",
        "ARCHIVED",
    }
