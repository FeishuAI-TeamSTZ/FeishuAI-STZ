"""业务对象层冒烟测试。

校验：
- 各 pydantic 业务对象可 instantiate
- ``Decision.from_orm() / .to_orm()`` round-trip 字段无丢失
- 区间约束（confidence ∈ [0,1] 等）由 pydantic 强制
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from memory_engine.models import DecisionModel
from memory_engine.types import (
    Card,
    CardAction,
    CardStatus,
    CardType,
    ConflictLevel,
    ConsensusSourceItem,
    Decision,
    DecisionAtom,
    DecisionState,
    EvolutionJudgment,
    EvolutionType,
    FeishuResponse,
    FiveFactors,
    GateResult,
    InterceptDecision,
    LLMCategory,
    LLMResponse,
    ProcessResult,
    Provenance,
    ReflectContext,
    ReflectReport,
    SourceType,
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def test_decision_atom_minimal() -> None:
    """DecisionAtom 七字段最小集合可构造。"""
    atom = DecisionAtom(
        subject="项目A",
        predicate="RELEASE_DATE",
        object="2026-05-15",
        logical_timestamp=_now(),
        provenance=Provenance.USER_STATED,
        confidence=0.95,
    )
    assert atom.subject == "项目A"
    assert atom.evolution_link is None


def test_decision_confidence_out_of_range_rejected() -> None:
    """pydantic 拒绝 confidence > 1。"""
    with pytest.raises(ValidationError):
        DecisionAtom(
            subject="s",
            predicate="p",
            object="o",
            logical_timestamp=_now(),
            provenance=Provenance.USER_STATED,
            confidence=1.5,
        )


def test_decision_from_orm_round_trip() -> None:
    """ORM Model → Decision 业务对象 → ORM Model，关键字段无丢失。"""
    now = _now()
    decision_id = uuid.uuid4()
    orm = DecisionModel(
        decision_id=decision_id,
        subject="项目A",
        predicate="RELEASE_DATE",
        object="2026-05-15",
        logical_timestamp=now,
        extracted_at=now,
        provenance=Provenance.USER_STATED,
        confidence=Decimal("0.95"),
        uncertainty=Decimal("0.10"),
        state=DecisionState.ACTIVE,
        evolution_type=EvolutionType.ROOT,
        consensus_sources=[],
        consensus_score=Decimal("0.00"),
        access_count=0,
        last_accessed_at=now,
        confirm_count=0,
        last_decay_calc_at=now,
        business_impact=Decimal("0.50"),
        created_at=now,
        updated_at=now,
    )

    biz = Decision.from_orm(orm)
    assert biz.decision_id == decision_id
    assert biz.subject == "项目A"
    # Decimal → float 收敛
    assert isinstance(biz.confidence, float)
    assert biz.confidence == pytest.approx(0.95)
    assert biz.uncertainty == pytest.approx(0.10)

    back = biz.to_orm()
    assert back.subject == "项目A"
    assert back.evolution_type is EvolutionType.ROOT


def test_evolution_judgment_root_low_confidence() -> None:
    """ROOT 判定可有 used_llm=False（OPPOSITE_PAIRS 命中跳过 LLM）。"""
    j = EvolutionJudgment(
        evolution_type=EvolutionType.ROOT,
        confidence=0.99,
        reasoning="无父决策候选",
        used_llm=False,
    )
    assert j.evolution_type is EvolutionType.ROOT


def test_reflect_report_calibration_can_be_negative() -> None:
    """confidence_calibration ∈ [-1, 1]，允许负值（下调置信度）。"""
    r = ReflectReport(
        quality_score=0.65,
        confidence_calibration=-0.15,
        reasoning="单源信号不足",
    )
    assert r.confidence_calibration == pytest.approx(-0.15)


def test_reflect_context_default_window_seven_days() -> None:
    atom = DecisionAtom(
        subject="s",
        predicate="p",
        object="o",
        logical_timestamp=_now(),
        provenance=Provenance.USER_STATED,
        confidence=0.7,
    )
    ctx = ReflectContext(candidate=atom)
    assert ctx.history_window_days == 7
    assert ctx.parent_pool == []


def test_five_factors_all_in_range() -> None:
    f = FiveFactors(
        f_freq=0.3,
        f_consensus=0.2,
        f_semantic=0.4,
        f_uncertainty=0.2,
        f_user_validation=0.1,
    )
    assert f.f_user_validation == pytest.approx(0.1)


def test_five_factors_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        FiveFactors(
            f_freq=0.3,
            f_consensus=0.2,
            f_semantic=0.4,
            f_uncertainty=0.2,
            f_user_validation=1.5,
        )


def test_card_quota_action_payload() -> None:
    card = Card(
        card_id=uuid.uuid4(),
        user_id="u1",
        decision_id=uuid.uuid4(),
        card_type=CardType.HARD_ASSERTION,
        status=CardStatus.QUEUED,
        priority_score=0.8,
        created_at=_now(),
    )
    assert card.status is CardStatus.QUEUED


def test_card_action_and_gate_result() -> None:
    action = CardAction(should_push=True, card_type=CardType.SOFT_INQUIRY)
    gate = GateResult(can_push=False, blocked_by="BUDGET")
    assert action.should_push
    assert gate.blocked_by == "BUDGET"


def test_llm_response_default_used_local_false() -> None:
    r = LLMResponse(content='{"k":1}', tokens_used=42, trace_id="trc_1", latency_ms=120)
    assert r.used_local is False


def test_feishu_response_data_default_empty() -> None:
    r = FeishuResponse(code=0, msg="ok", trace_id="trc_2", latency_ms=80)
    assert r.data == {}


def test_process_result_defaults_zero() -> None:
    r = ProcessResult()
    assert r.llm_calls == 0
    assert r.decisions_extracted == []


def test_intercept_decision_block_action() -> None:
    d = InterceptDecision(
        action="BLOCK",
        reason="Q3 冻结发布",
        decision_ids=[uuid.uuid4()],
        trace_id="trc_cli_1",
        rendered_card="❌ 拦截：...",
    )
    assert d.action == "BLOCK"


def test_consensus_source_item() -> None:
    item = ConsensusSourceItem(
        source_type=SourceType.OKR,
        uri="feishu://okr/Q3-001",
        weight=0.4,
        extracted_at=_now(),
    )
    assert item.source_type is SourceType.OKR


def test_business_enums_disjoint() -> None:
    """3 个业务专属 enum 各自不同。"""
    assert {c.value for c in LLMCategory} == {
        "extract_light",
        "evolve_heavy",
        "reflect_border",
        "cross_align",
        "decay_offline",
    }
    assert ConflictLevel.HARD.value == "HARD"
    assert SourceType.OKR.value == "feishu_okr"
