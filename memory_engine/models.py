"""SQLAlchemy 2.0 ORM 模型，与 ``schema.sql`` 1:1 镜像。

风格：``Mapped[Type] + DeclarativeBase``（现代式，与 mypy --strict 兼容）。

约定（04-ENGUIDE §3）：
- 每张表一个 ``<Entity>Model`` 类；类名后缀 ``Model`` 区分于 pydantic 业务对象（types.py，T-003）
- ORM 模型不出 ``memory_engine`` 包；外层只见 pydantic 业务对象
- 所有 enum 在 Python 端定义，与 SQL enum literal 严格对齐（值即字符串）

不变量落点（03-SCHEMA §9）：
- W2: ``decisions`` 的 ``chk_decisions_evolution_parent`` CHECK
- W13: ``trace_log.trace_id`` PK NOT NULL
- W14: ``card_quota.chk_card_quota_count`` CHECK ≤ ``max_daily``
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


# ============================================================
# Enums (Python 端 ↔ SQL enum literal 严格 1:1)
# ============================================================


class Provenance(str, enum.Enum):
    """决策原子的来源信任档（六档；权重见 ``config.PROVENANCE_TRUST_WEIGHTS``，T-003）。"""

    USER_STATED = "USER_STATED"
    OKR_SYNCED = "OKR_SYNCED"
    APPROVAL_PASSED = "APPROVAL_PASSED"
    DOC_SYNCED = "DOC_SYNCED"
    MEETING_EXTRACTED = "MEETING_EXTRACTED"
    SYSTEM_INFERRED = "SYSTEM_INFERRED"


class EvolutionType(str, enum.Enum):
    """演化关系类型；ROOT 表无父，其余四个必须有 parent_id（W2 CHECK）。"""

    ROOT = "ROOT"
    SUPERSEDES = "SUPERSEDES"
    REFINES = "REFINES"
    GENERALIZES = "GENERALIZES"
    BRANCHES = "BRANCHES"


class DecisionState(str, enum.Enum):
    """决策原子的状态机（5 态；状态转换由 ``state_machine.py`` 单点驱动，T-005）。"""

    ACTIVE = "ACTIVE"
    STALE = "STALE"
    HYPOTHESIS = "HYPOTHESIS"
    GHOST = "GHOST"
    ARCHIVED = "ARCHIVED"


class CardType(str, enum.Enum):
    """卡片分类（02-DESIGN §四 机制六）。"""

    HARD_ASSERTION = "HARD_ASSERTION"
    SOFT_INQUIRY = "SOFT_INQUIRY"
    GHOST_LOG = "GHOST_LOG"
    CROSS_SYSTEM_ALERT = "CROSS_SYSTEM_ALERT"
    EVOLUTION_NOTICE = "EVOLUTION_NOTICE"


class CardStatus(str, enum.Enum):
    """卡片状态机（受 W14 / W15 闸门控制）。"""

    QUEUED = "QUEUED"
    PUSHED = "PUSHED"
    RESPONDED = "RESPONDED"
    EXPIRED = "EXPIRED"


class CardResponse(str, enum.Enum):
    """用户对卡片的响应；CONFIRMED 触发 W8 全量清零（``decay.handle_w8_reset``）。"""

    CONFIRMED = "CONFIRMED"
    DENIED = "DENIED"
    NO_RESPONSE_24H = "NO_RESPONSE_24H"
    IGNORED = "IGNORED"


# 复用 schema.sql 已定义的 enum 类型（不让 SQLAlchemy 重建）
_PROV_SQL = ENUM(Provenance, name="provenance_enum", create_type=False)
_EVO_SQL = ENUM(EvolutionType, name="evolution_type_enum", create_type=False)
_STATE_SQL = ENUM(DecisionState, name="decision_state_enum", create_type=False)
_CTYPE_SQL = ENUM(CardType, name="card_type_enum", create_type=False)
_CSTATUS_SQL = ENUM(CardStatus, name="card_status_enum", create_type=False)
_CRESP_SQL = ENUM(CardResponse, name="card_response_enum", create_type=False)


# ============================================================
# Models（按 schema.sql 中的 FK 依赖顺序）
# ============================================================


class UserModel(Base):
    """用户档案（schema.sql §3.1）。"""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feishu_user_id: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'Asia/Shanghai'")
    )
    work_hour_start: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("9")
    )
    work_hour_end: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("19")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("work_hour_start BETWEEN 0 AND 23", name="chk_users_work_hour_start"),
        CheckConstraint(
            "work_hour_end BETWEEN 1 AND 24 AND work_hour_end > work_hour_start",
            name="chk_users_work_hour_end",
        ),
        Index(
            "idx_users_feishu_id",
            "feishu_user_id",
            unique=True,
            postgresql_where=text("feishu_user_id IS NOT NULL"),
        ),
    )


class TraceLogModel(Base):
    """飞书 API trace（schema.sql §3.2，**W13 在 DB 层强制**：``trace_id`` PK NOT NULL）。"""

    __tablename__ = "trace_log"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    called_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("direction IN ('OUT', 'IN', 'HOOK')", name="chk_trace_direction"),
        Index("idx_trace_called_at", "called_at"),
        Index("idx_trace_endpoint", "api_endpoint", "called_at"),
    )


class DecisionModel(Base):
    """决策原子主表（schema.sql §3.3，**W2 在 DB 层强制**）。"""

    __tablename__ = "decisions"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False)
    object: Mapped[str] = mapped_column(Text, nullable=False)
    logical_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    provenance: Mapped[Provenance] = mapped_column(_PROV_SQL, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    uncertainty: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.00")
    )
    state: Mapped[DecisionState] = mapped_column(
        _STATE_SQL, nullable=False, server_default=text("'ACTIVE'")
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.decision_id", ondelete="RESTRICT"),
    )
    evolution_type: Mapped[EvolutionType] = mapped_column(_EVO_SQL, nullable=False)
    consensus_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    consensus_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.00")
    )
    source_event_id: Mapped[str | None] = mapped_column(Text)
    original_text: Mapped[str | None] = mapped_column(Text)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_accessed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    confirm_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_decay_calc_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    business_impact: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.50")
    )
    owner_user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    # 自引用：parent 可解析为另一条决策；远端键即自身主键
    parent: Mapped[DecisionModel | None] = relationship(
        "DecisionModel", remote_side="DecisionModel.decision_id"
    )

    __table_args__ = (
        CheckConstraint(
            "(evolution_type = 'ROOT' AND parent_id IS NULL) OR "
            "(evolution_type IN ('SUPERSEDES', 'REFINES', 'GENERALIZES', 'BRANCHES') "
            "AND parent_id IS NOT NULL)",
            name="chk_decisions_evolution_parent",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="chk_decisions_confidence"),
        CheckConstraint("uncertainty BETWEEN 0 AND 1", name="chk_decisions_uncertainty"),
        CheckConstraint("consensus_score BETWEEN 0 AND 1", name="chk_decisions_consensus_score"),
        CheckConstraint("business_impact BETWEEN 0 AND 1", name="chk_decisions_business_impact"),
        CheckConstraint(
            "access_count >= 0 AND confirm_count >= 0",
            name="chk_decisions_counts_nonneg",
        ),
        Index("idx_decisions_subj_pred_state", "subject", "predicate", "state"),
        Index("idx_decisions_state_decay", "state", "last_decay_calc_at"),
        Index(
            "idx_decisions_owner_state",
            "owner_user_id",
            "state",
            postgresql_where=text("state IN ('ACTIVE', 'STALE', 'HYPOTHESIS')"),
        ),
        Index(
            "idx_decisions_parent",
            "parent_id",
            postgresql_where=text("parent_id IS NOT NULL"),
        ),
    )


class DecisionEmbeddingModel(Base):
    """决策原子的语义向量（schema.sql §3.4，pgvector v1，1024 维）。"""

    __tablename__ = "decision_embeddings"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.decision_id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(32))
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class CardQuotaModel(Base):
    """每日打扰预算（schema.sql §3.5，**W14 在 DB 层强制** count ≤ max_daily）。"""

    __tablename__ = "card_quota"

    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), primary_key=True)
    quota_date: Mapped[date] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_daily: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("count >= 0 AND count <= max_daily", name="chk_card_quota_count"),
    )


class CardModel(Base):
    """推送卡片（schema.sql §3.6）。"""

    __tablename__ = "cards"

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.decision_id"),
        nullable=False,
    )
    related_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.decision_id")
    )
    card_type: Mapped[CardType] = mapped_column(_CTYPE_SQL, nullable=False)
    status: Mapped[CardStatus] = mapped_column(
        _CSTATUS_SQL, nullable=False, server_default=text("'QUEUED'")
    )
    priority_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.00")
    )
    response: Mapped[CardResponse | None] = mapped_column(_CRESP_SQL)
    pushed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    trace_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("trace_log.trace_id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "(status = 'RESPONDED') = (response IS NOT NULL)",
            name="chk_cards_response_consistency",
        ),
        CheckConstraint(
            "(status IN ('PUSHED', 'RESPONDED', 'EXPIRED')) = (pushed_at IS NOT NULL)",
            name="chk_cards_pushed_consistency",
        ),
        CheckConstraint("priority_score BETWEEN 0 AND 1", name="chk_cards_priority"),
        Index("idx_cards_user_status", "user_id", "status"),
        Index(
            "idx_cards_dedup",
            "decision_id",
            "related_decision_id",
            "pushed_at",
            postgresql_where=text("status IN ('PUSHED', 'RESPONDED')"),
        ),
    )


class ReflectLogModel(Base):
    """Reflect Agent 质量档案（schema.sql §3.7，W6: 只 INSERT，不 UPDATE 历史）。"""

    __tablename__ = "reflect_logs"

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.decision_id"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.decision_id")
    )
    original_evolution_type: Mapped[EvolutionType | None] = mapped_column(_EVO_SQL)
    quality_score: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    potential_missed_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.decision_id")
    )
    suggested_type: Mapped[EvolutionType | None] = mapped_column(_EVO_SQL)
    confidence_calibration: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("0.000")
    )
    reasoning: Mapped[str | None] = mapped_column(String(255))
    evaluated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("quality_score BETWEEN 0 AND 1", name="chk_reflect_quality"),
        CheckConstraint(
            "confidence_calibration BETWEEN -1 AND 1",
            name="chk_reflect_calibration",
        ),
        Index("idx_reflect_decision_time", "decision_id", "evaluated_at"),
        Index("idx_reflect_quality", "quality_score"),
    )


class DecayCalculationModel(Base):
    """五维 λ 审计日志（schema.sql §3.8，含 5 因子 + 前后 uncertainty + reason）。"""

    __tablename__ = "decay_calculations"

    calc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.decision_id"),
        nullable=False,
    )
    lambda_value: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    f_freq: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    f_consensus: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    f_semantic: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    f_uncertainty: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    f_user_validation: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    prev_uncertainty: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    new_uncertainty: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_decay_decision_time", "decision_id", "calculated_at"),
        Index("idx_decay_time", "calculated_at"),
    )


__all__ = [
    "Base",
    # Enums
    "Provenance",
    "EvolutionType",
    "DecisionState",
    "CardType",
    "CardStatus",
    "CardResponse",
    # Models
    "UserModel",
    "TraceLogModel",
    "DecisionModel",
    "DecisionEmbeddingModel",
    "CardQuotaModel",
    "CardModel",
    "ReflectLogModel",
    "DecayCalculationModel",
]
