"""业务对象层（pydantic v2）。

数据三层（04-ENGUIDE §3）：
    DTO（边界）  ──►  业务对象（本模块）  ──►  ORM（``models.py``）

约定：
- 业务对象只在 ``memory_engine`` 内部流通；不出包就不接触 DTO，不持有 Session
- ORM Enum（来源 ``models.py``）在此 re-export，对外接口不再 import models
- ``Decision.from_orm()`` / ``to_orm()`` 是 ORM ↔ 业务对象唯一转换桥
- 业务侧不用 ``Decimal``，置信度 / uncertainty / 权重一律 ``float``，``from_orm`` 时收敛

接口锚点（04-ENGUIDE §8）：
- §8.1  ``DecisionAtom``  M1 提取出参
- §8.2  ``EvolutionJudgment``  M2 演化判定出参
- §8.3  ``ReflectReport`` / ``ReflectContext``  M3 Reflect
- §8.5  ``Decision``  Hot Path 返回
- §8.6  ``ProcessResult``  Cold Path 返回
- §8.7  ``Card`` / ``CardAction`` / ``GateResult``  M6 卡片
- §8.8  ``FiveFactors``  M7 衰减因子
- §8.9  ``LLMResponse`` / ``LLMCategory`` / ``FeishuResponse``  共享工具
- §8.10 ``InterceptDecision``  CLI Hook
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ORM enum：在 types 层 re-export，让外层只 import 一处
from .models import (
    CardResponse,
    CardStatus,
    CardType,
    DecisionState,
    EvolutionType,
    Provenance,
)

if TYPE_CHECKING:
    from .models import DecisionModel


# ============================================================
# 业务专属 Enum（不入 SQL）
# ============================================================


class LLMCategory(str, enum.Enum):
    """LLM 调用分类（04-ENGUIDE §8.9 + §4.4 预算表）。"""

    EXTRACT_LIGHT = "extract_light"
    EVOLVE_HEAVY = "evolve_heavy"
    REFLECT_BORDER = "reflect_border"
    CROSS_ALIGN = "cross_align"
    DECAY_OFFLINE = "decay_offline"


class SourceType(str, enum.Enum):
    """跨源 source 类型（03-SCHEMA §2.7：jsonb 内字符串集合，不入 SQL enum）。

    ``CONSENSUS_WEIGHTS`` 的键，W9 要求 OKR 顶档。
    """

    OKR = "feishu_okr"
    DOC = "feishu_doc"
    MESSAGE = "feishu_message"
    CALENDAR = "feishu_calendar"
    APPROVAL = "feishu_approval"
    MINUTES = "feishu_minutes"
    CLI_EVENT = "cli_event"


class ConflictLevel(str, enum.Enum):
    """卡片决策树用的冲突等级（04-ENGUIDE §8.7 ``classify_conflict`` 出参）。"""

    HARD = "HARD"
    SOFT = "SOFT"
    NONE = "NONE"


# ============================================================
# 通用 type alias / 子模型
# ============================================================

# 置信度 / uncertainty / 权重的统一区间约束
ConfidenceFloat = Annotated[float, Field(ge=0.0, le=1.0)]
CalibrationFloat = Annotated[float, Field(ge=-1.0, le=1.0)]


class ConsensusSourceItem(BaseModel):
    """``decisions.consensus_sources`` jsonb 数组的单条目（03-SCHEMA §3.1）。"""

    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    uri: str
    weight: ConfidenceFloat
    extracted_at: datetime


# ============================================================
# 决策原子 ── 提取阶段（M1）→ 落库后（M2 commit_evolution 之后）
# ============================================================


class DecisionAtom(BaseModel):
    """七字段决策原子（M1 提取出参；尚未落库，无 ``decision_id``）。"""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=255)
    predicate: str = Field(min_length=1, max_length=255)
    object: str = Field(min_length=1)
    logical_timestamp: datetime
    provenance: Provenance
    confidence: ConfidenceFloat
    evolution_link: UUID | None = None
    """演化链锚点：M1 提取阶段一般为 None；M2 ``find_potential_parents`` 命中后由 cold_path 注入。"""
    source_event_id: str | None = None
    original_text: str | None = None


class Decision(BaseModel):
    """落库后的决策（含 ``decision_id`` + 状态 + 五维输入）。Hot Path 返回类型。"""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    subject: str
    predicate: str
    object: str
    logical_timestamp: datetime
    extracted_at: datetime
    provenance: Provenance
    confidence: ConfidenceFloat
    uncertainty: ConfidenceFloat = 0.0
    state: DecisionState = DecisionState.ACTIVE
    parent_id: UUID | None = None
    evolution_type: EvolutionType
    consensus_sources: list[ConsensusSourceItem] = Field(default_factory=list)
    consensus_score: ConfidenceFloat = 0.0
    source_event_id: str | None = None
    original_text: str | None = None
    access_count: int = Field(default=0, ge=0)
    last_accessed_at: datetime
    confirm_count: int = Field(default=0, ge=0)
    last_confirmed_at: datetime | None = None
    last_decay_calc_at: datetime
    business_impact: ConfidenceFloat = 0.5
    owner_user_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "confidence", "uncertainty", "consensus_score", "business_impact", mode="before"
    )
    @classmethod
    def _decimal_to_float(cls, v: Any) -> Any:
        """ORM 端 ``Numeric(3,2)`` 返回 ``Decimal``；业务侧统一 ``float``。"""
        return float(v) if isinstance(v, Decimal) else v

    @classmethod
    def from_orm(cls, model: DecisionModel) -> Decision:
        """ORM Model → 业务对象。``parent`` relationship 不递归（M2 真接入时再处理）。"""
        return cls.model_validate(model, from_attributes=True)

    def to_orm(self) -> DecisionModel:
        """业务对象 → ORM Model。仅产出新行用；UPDATE 仍走 service 层。"""
        from .models import DecisionModel as _DM

        data = self.model_dump(exclude_none=False)
        # consensus_sources 在业务层是 list[ConsensusSourceItem]；ORM 侧需要 list[dict]
        data["consensus_sources"] = [
            item.model_dump(mode="json") for item in self.consensus_sources
        ]
        return _DM(**data)


# ============================================================
# 演化判定（M2）+ Reflect（M3）
# ============================================================


class EvolutionJudgment(BaseModel):
    """演化判定结果（04-ENGUIDE §8.2 ``judge_evolution`` 出参）。"""

    model_config = ConfigDict(extra="forbid")

    evolution_type: EvolutionType
    confidence: ConfidenceFloat
    reasoning: str = Field(max_length=200)
    used_llm: bool


class ReflectContext(BaseModel):
    """Reflect 输入上下文（04-ENGUIDE §8.3）。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    candidate: DecisionAtom
    parent_pool: list[Decision] = Field(default_factory=list)
    history_window_days: int = Field(default=7, ge=1, le=90)


class ReflectReport(BaseModel):
    """Reflect 评估报告；W6: 仅 INSERT ``reflect_logs``，绝不 UPDATE 决策历史。"""

    model_config = ConfigDict(extra="forbid")

    quality_score: ConfidenceFloat
    potential_missed_parent_id: UUID | None = None
    suggested_type: EvolutionType | None = None
    confidence_calibration: CalibrationFloat = 0.0
    reasoning: str = Field(max_length=200)


# ============================================================
# 卡片（M6）+ 五维（M7）
# ============================================================


class FiveFactors(BaseModel):
    """五维衰减因子（02-DESIGN §四 机制七 + 03-SCHEMA §5.1，5 因子已锁）。"""

    model_config = ConfigDict(extra="forbid")

    f_freq: ConfidenceFloat
    f_consensus: ConfidenceFloat
    f_semantic: ConfidenceFloat
    f_uncertainty: ConfidenceFloat
    f_user_validation: ConfidenceFloat


class Card(BaseModel):
    """卡片业务对象（M6 enqueue / push 流转）。"""

    model_config = ConfigDict(extra="forbid")

    card_id: UUID
    user_id: str
    decision_id: UUID
    related_decision_id: UUID | None = None
    card_type: CardType
    status: CardStatus = CardStatus.QUEUED
    priority_score: ConfidenceFloat = 0.0
    response: CardResponse | None = None
    pushed_at: datetime | None = None
    responded_at: datetime | None = None
    trace_id: str | None = None
    created_at: datetime


class CardAction(BaseModel):
    """``decide_card_action`` 出参（04-ENGUIDE §8.7）。"""

    model_config = ConfigDict(extra="forbid")

    should_push: bool
    card_type: CardType


class GateResult(BaseModel):
    """``gate_check`` 出参（W11 / W14 / W15 闸门，04-ENGUIDE §8.7）。"""

    model_config = ConfigDict(extra="forbid")

    can_push: bool
    blocked_by: Literal["BUDGET", "WORK_HOURS", "DEDUP_24H"] | None = None


# ============================================================
# 共享工具响应（§8.9）
# ============================================================


class LLMResponse(BaseModel):
    """LLM 网关返回（04-ENGUIDE §8.9）。``used_local=True`` 表 W12 已降级。"""

    model_config = ConfigDict(extra="forbid")

    content: str
    tokens_used: int = Field(ge=0)
    used_local: bool = False
    trace_id: str
    latency_ms: int = Field(ge=0)


class FeishuResponse(BaseModel):
    """飞书 API 网关返回（W13 强制写 ``trace_log``）。"""

    model_config = ConfigDict(extra="forbid")

    code: int
    msg: str
    data: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    latency_ms: int = Field(ge=0)


# ============================================================
# 编排返回（§8.6 / §8.10）
# ============================================================


class ProcessResult(BaseModel):
    """``cold_path.process_event`` 出参（04-ENGUIDE §8.6）。"""

    model_config = ConfigDict(extra="forbid")

    decisions_extracted: list[UUID] = Field(default_factory=list)
    cards_queued: list[UUID] = Field(default_factory=list)
    consensus_alerts: list[UUID] = Field(default_factory=list)
    llm_calls: int = Field(default=0, ge=0)


class InterceptDecision(BaseModel):
    """CLI Hook ``pre_command_hook`` 出参（04-ENGUIDE §8.10）。"""

    model_config = ConfigDict(extra="forbid")

    action: Literal["ALLOW", "BLOCK", "WARN"]
    reason: str | None = None
    decision_ids: list[UUID] = Field(default_factory=list)
    trace_id: str
    rendered_card: str | None = None


__all__ = [
    # ORM enum re-export
    "Provenance",
    "EvolutionType",
    "DecisionState",
    "CardType",
    "CardStatus",
    "CardResponse",
    # 业务专属 enum
    "LLMCategory",
    "SourceType",
    "ConflictLevel",
    # 子模型
    "ConsensusSourceItem",
    # 决策原子 / 决策
    "DecisionAtom",
    "Decision",
    # 演化 / Reflect
    "EvolutionJudgment",
    "ReflectContext",
    "ReflectReport",
    # 卡片 / 五维
    "FiveFactors",
    "Card",
    "CardAction",
    "GateResult",
    # 共享工具响应
    "LLMResponse",
    "FeishuResponse",
    # 编排
    "ProcessResult",
    "InterceptDecision",
]
