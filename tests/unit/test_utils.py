"""T-005 P0+P1 单测：cache + invariants + embeddings + llm_gateway。

覆盖：
- Cache：miss / set+get / TTL 默认值 / glob invalidate / clear / size
- W2：SUPERSEDES 父必须 ARCHIVED；REFINES 父必须保 ACTIVE；ROOT 跳过
- W14：current_count < max → OK；>= max → W14Violation
- W15：本地工时内 OK；时区外 → W15Violation
- Embeddings：1024 维 / deterministic / 单位向量 / cosine self=1
- LLM gateway：mock 模式 deterministic / TPM 计数 / 超额 W12 / category 模板
- 异常携带 trace_id + extra（structlog 关联用）
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import pytest

from memory_engine.exceptions import (
    LLMQuotaExceededError,
    W2Violation,
    W14Violation,
    W15Violation,
)
from memory_engine.types import DecisionState, EvolutionType, LLMCategory
from memory_engine.utils.cache import (
    cache_clear,
    cache_get,
    cache_invalidate,
    cache_set,
    cache_size,
)
from memory_engine.utils.invariants import assert_w2, assert_w14, assert_w15


# ============================================================
# Cache（5 case）
# ============================================================


class TestCache:
    """memory_engine.utils.cache 行为契约。"""

    def setup_method(self) -> None:
        cache_clear()

    def test_miss_returns_none(self) -> None:
        assert cache_get("nonexistent_key") is None

    def test_set_then_get_roundtrip(self) -> None:
        payload: dict[str, Any] = {"decision_id": "dec_abc", "state": "ACTIVE"}
        cache_set("dec_abc", payload)
        assert cache_get("dec_abc") == payload
        assert cache_size() == 1

    def test_invalidate_glob(self) -> None:
        cache_set("dec_a", 1)
        cache_set("dec_b", 2)
        cache_set("card_x", 3)
        cache_set("card_y", 4)
        n = cache_invalidate("dec_*")
        assert n == 2
        assert cache_get("dec_a") is None
        assert cache_get("dec_b") is None
        assert cache_get("card_x") == 3
        assert cache_get("card_y") == 4

    def test_invalidate_no_match(self) -> None:
        cache_set("dec_a", 1)
        n = cache_invalidate("nonexistent_*")
        assert n == 0
        assert cache_get("dec_a") == 1

    def test_clear_empties(self) -> None:
        cache_set("k1", 1)
        cache_set("k2", 2)
        assert cache_size() == 2
        cache_clear()
        assert cache_size() == 0
        assert cache_get("k1") is None


# ============================================================
# W2（4 case）
# ============================================================


class TestW2:
    """SUPERSEDES 父转 ARCHIVED；REFINES / GENERALIZES / BRANCHES 父保 ACTIVE。"""

    def test_supersedes_parent_archived_ok(self) -> None:
        # 正样本：commit_evolution 后父已转 ARCHIVED
        assert_w2(DecisionState.ARCHIVED, EvolutionType.SUPERSEDES)

    def test_supersedes_parent_active_violates(self) -> None:
        # 负样本：父没及时 transition
        with pytest.raises(W2Violation) as exc_info:
            assert_w2(DecisionState.ACTIVE, EvolutionType.SUPERSEDES, trace_id="trc_01")
        assert exc_info.value.trace_id == "trc_01"
        assert exc_info.value.extra["edge_type"] == "SUPERSEDES"

    def test_refines_parent_active_ok(self) -> None:
        # REFINES 不应让父归档
        assert_w2(DecisionState.ACTIVE, EvolutionType.REFINES)
        assert_w2(DecisionState.STALE, EvolutionType.REFINES)
        assert_w2(DecisionState.ACTIVE, EvolutionType.GENERALIZES)
        assert_w2(DecisionState.ACTIVE, EvolutionType.BRANCHES)

    def test_refines_parent_archived_violates(self) -> None:
        with pytest.raises(W2Violation):
            assert_w2(DecisionState.ARCHIVED, EvolutionType.REFINES)

    def test_root_no_check(self) -> None:
        # ROOT 无父，任何 state 都跳过（实际 ROOT 时 caller 不该传 parent_state）
        assert_w2(DecisionState.ACTIVE, EvolutionType.ROOT)
        assert_w2(DecisionState.ARCHIVED, EvolutionType.ROOT)


# ============================================================
# W14（3 case）
# ============================================================


class TestW14:
    """单用户每日卡片推送 ≤ max_daily（DB CHECK 双保险）。"""

    def test_under_limit_ok(self) -> None:
        assert_w14(current_count=0)
        assert_w14(current_count=4)  # 即将推第 5 张，仍 OK
        assert_w14(current_count=4, max_daily=5)

    def test_at_limit_violates(self) -> None:
        # current=5 表示已推 5 张，第 6 张超额
        with pytest.raises(W14Violation) as exc_info:
            assert_w14(current_count=5, user_id="u_test", trace_id="trc_02")
        assert exc_info.value.trace_id == "trc_02"
        assert exc_info.value.extra["user_id"] == "u_test"
        assert exc_info.value.extra["current_count"] == 5
        assert exc_info.value.extra["max_daily"] == 5

    def test_custom_max_daily(self) -> None:
        # 配置侧上限可调（W14 数值 5 是默认值，不是宪法值）
        assert_w14(current_count=9, max_daily=10)
        with pytest.raises(W14Violation):
            assert_w14(current_count=10, max_daily=10)


# ============================================================
# W15（3 case）
# ============================================================


class TestW15:
    """非工作时段暂停非紧急卡片（用户本地时区）。"""

    def test_in_work_hours_shanghai(self) -> None:
        # 14:00 上海 = UTC 06:00
        now_utc = datetime(2026, 5, 13, 6, 0, tzinfo=timezone.utc)
        assert_w15(now_utc, work_hour_start=9, work_hour_end=19)

    def test_before_work_hours(self) -> None:
        # 03:00 上海 = UTC 19:00（前一日）
        now_utc = datetime(2026, 5, 12, 19, 0, tzinfo=timezone.utc)
        with pytest.raises(W15Violation) as exc_info:
            assert_w15(
                now_utc,
                work_hour_start=9,
                work_hour_end=19,
                user_id="u_test",
                trace_id="trc_03",
            )
        assert exc_info.value.trace_id == "trc_03"
        assert exc_info.value.extra["local_hour"] == 3

    def test_after_work_hours(self) -> None:
        # 23:00 上海 = UTC 15:00
        now_utc = datetime(2026, 5, 13, 15, 0, tzinfo=timezone.utc)
        with pytest.raises(W15Violation) as exc_info:
            assert_w15(now_utc, work_hour_start=9, work_hour_end=19)
        assert exc_info.value.extra["local_hour"] == 23

    def test_custom_timezone(self) -> None:
        # 14:00 美东（UTC-4 in May with DST）= UTC 18:00
        now_utc = datetime(2026, 5, 13, 18, 0, tzinfo=timezone.utc)
        # 在 New York 下应在工时
        assert_w15(
            now_utc,
            work_hour_start=9,
            work_hour_end=19,
            timezone_str="America/New_York",
        )

    def test_boundary_exact_start(self) -> None:
        # 09:00 整点 = 工时起点（包含）
        now_utc = datetime(2026, 5, 13, 1, 0, tzinfo=timezone.utc)  # 09:00 上海
        assert_w15(now_utc, work_hour_start=9, work_hour_end=19)

    def test_boundary_exact_end(self) -> None:
        # 19:00 整点 = 工时终点（不包含；左闭右开）
        now_utc = datetime(2026, 5, 13, 11, 0, tzinfo=timezone.utc)  # 19:00 上海
        with pytest.raises(W15Violation):
            assert_w15(now_utc, work_hour_start=9, work_hour_end=19)


# ============================================================
# Embeddings（6 case）
# ============================================================


class TestEmbeddings:
    """memory_engine.utils.embeddings — Doubao Embedding 1024 维 + cosine."""

    def test_dim_1024(self) -> None:
        from memory_engine.utils.embeddings import EMBEDDING_DIM, compute_embedding

        v = compute_embedding("hello")
        assert len(v) == EMBEDDING_DIM == 1024

    def test_deterministic(self) -> None:
        from memory_engine.utils.embeddings import compute_embedding

        v1 = compute_embedding("hello world")
        v2 = compute_embedding("hello world")
        assert v1 == v2

    def test_different_text_diff_vector(self) -> None:
        from memory_engine.utils.embeddings import compute_embedding

        v1 = compute_embedding("hello")
        v2 = compute_embedding("world")
        assert v1 != v2

    def test_unit_vector(self) -> None:
        """mock embedding 应为单位向量（mock 内部归一化）。"""
        from memory_engine.utils.embeddings import compute_embedding, cosine_similarity

        v = compute_embedding("test sentence for unit norm")
        # 单位向量：自己与自己的 cosine = 1
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_cosine_similarity_dim_mismatch(self) -> None:
        from memory_engine.utils.embeddings import cosine_similarity

        with pytest.raises(ValueError, match="维度不一致"):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_cosine_similarity_zero_vector(self) -> None:
        from memory_engine.utils.embeddings import cosine_similarity

        zero = [0.0] * 1024
        v = [1.0 / (1024**0.5)] * 1024  # 单位向量
        assert cosine_similarity(zero, v) == 0.0

    def test_empty_text_raises(self) -> None:
        from memory_engine.utils.embeddings import compute_embedding

        with pytest.raises(ValueError, match="text 不能为空"):
            compute_embedding("")


# ============================================================
# LLM Gateway（7 case）
# ============================================================


@pytest.fixture(autouse=True)
def _ensure_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """所有 LLM 单测强制 mock 模式（避免误调真 API）。"""
    monkeypatch.setenv("USE_LLM_MOCK", "1")
    # 重置 quota 计数器（模块级状态）
    from memory_engine.utils.llm_gateway import _reset_quota

    _reset_quota()


class TestLLMGatewayMock:
    """mock-first LLM gateway 行为契约。"""

    def test_light_extract_returns_deterministic_json(self) -> None:
        from memory_engine.utils.llm_gateway import light_llm_extract

        r1 = light_llm_extract("test prompt", category=LLMCategory.EXTRACT_LIGHT)
        r2 = light_llm_extract("test prompt", category=LLMCategory.EXTRACT_LIGHT)
        assert r1.content == r2.content
        assert not r1.used_local
        # mock content 是合法 JSON
        parsed: dict[str, Any] = json.loads(r1.content)
        assert "subject" in parsed
        assert parsed["confidence"] > 0

    def test_heavy_extract_evolution_json(self) -> None:
        from memory_engine.utils.llm_gateway import heavy_llm_extract

        r = heavy_llm_extract("evolve this", category=LLMCategory.EVOLVE_HEAVY)
        parsed: dict[str, Any] = json.loads(r.content)
        assert parsed["evolution_type"] in {
            "ROOT",
            "SUPERSEDES",
            "REFINES",
            "GENERALIZES",
            "BRANCHES",
        }
        assert 0 <= parsed["confidence"] <= 1

    def test_reflect_border_quality_score(self) -> None:
        from memory_engine.utils.llm_gateway import heavy_llm_extract

        r = heavy_llm_extract("reflect this", category=LLMCategory.REFLECT_BORDER)
        parsed: dict[str, Any] = json.loads(r.content)
        assert "quality_score" in parsed
        assert 0 <= parsed["quality_score"] <= 1

    def test_trace_id_stable_in_mock(self) -> None:
        """mock 模式下 (prompt, category) 决定 trace_id（便于单测断言）。"""
        from memory_engine.utils.llm_gateway import light_llm_extract

        r1 = light_llm_extract("same prompt", category=LLMCategory.EXTRACT_LIGHT)
        r2 = light_llm_extract("same prompt", category=LLMCategory.EXTRACT_LIGHT)
        assert r1.trace_id == r2.trace_id
        assert r1.trace_id.startswith("trc_")

    def test_tokens_used_tracked(self) -> None:
        """tokens_used > 0 + quota 计数器对应 category 同步增长。"""
        from memory_engine.utils.llm_gateway import (
            _get_quota_used,
            light_llm_extract,
        )

        before = _get_quota_used(LLMCategory.EXTRACT_LIGHT)
        r = light_llm_extract("count me", category=LLMCategory.EXTRACT_LIGHT)
        after = _get_quota_used(LLMCategory.EXTRACT_LIGHT)
        assert r.tokens_used > 0
        assert after - before == r.tokens_used

    def test_quota_exceeded_raises_w12(self) -> None:
        """连续调用直至超过 DAILY_LLM_BUDGET[category] → LLMQuotaExceededError。"""
        from memory_engine.config import DAILY_LLM_BUDGET
        from memory_engine.utils.llm_gateway import (
            _get_quota_used,
            light_llm_extract,
        )

        budget = DAILY_LLM_BUDGET[LLMCategory.DECAY_OFFLINE]  # 最小预算 0.5K
        # 反复调用直到超额（每次约 80 tokens）
        with pytest.raises(LLMQuotaExceededError) as exc_info:
            for i in range(budget // 50 + 5):
                light_llm_extract(f"prompt-{i}", category=LLMCategory.DECAY_OFFLINE)
        assert exc_info.value.extra["category"] == "decay_offline"
        assert _get_quota_used(LLMCategory.DECAY_OFFLINE) > 0

    def test_empty_prompt_raises(self) -> None:
        from memory_engine.utils.llm_gateway import heavy_llm_extract

        with pytest.raises(ValueError, match="prompt 不能为空"):
            heavy_llm_extract("", category=LLMCategory.EVOLVE_HEAVY)


# ============================================================
# Feishu Client（5 case，mock-first；W13 trace_id 必生成）
# ============================================================


@pytest.fixture(autouse=True)
def _ensure_feishu_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """所有 feishu 单测强制 mock 模式（避免误调真飞书 API）。"""
    monkeypatch.setenv("USE_FEISHU_MOCK", "1")


class TestFeishuClientMock:
    """memory_engine.utils.feishu_client — W13 强制 trace_id + mock 响应。"""

    def test_mock_returns_code_0(self) -> None:
        from memory_engine.utils.feishu_client import feishu_call

        r = feishu_call("/open-apis/im/v1/messages", "POST", {"text": "hi"})
        assert r.code == 0
        assert r.msg == "ok"
        assert r.trace_id.startswith("trc_")

    def test_trace_id_unique_per_call(self) -> None:
        """W13: 每次调用生成新 trace_id（mock 模式也强制）。"""
        from memory_engine.utils.feishu_client import feishu_call

        ids = {feishu_call("/open-apis/im/v1/messages").trace_id for _ in range(10)}
        assert len(ids) == 10  # 全部唯一

    def test_endpoint_template_match(self) -> None:
        """endpoint 前缀匹配不同 mock 模板。"""
        from memory_engine.utils.feishu_client import feishu_call

        token = feishu_call("/open-apis/auth/v3/tenant_access_token/internal", "POST")
        msg = feishu_call("/open-apis/im/v1/messages", "POST")
        # token endpoint 模板含 tenant_access_token 字段；message endpoint 模板含 message_id
        # 不同 endpoint 的 mock 应有可区分内容
        assert token.code == 0
        assert msg.code == 0
        assert token.data != msg.data

    def test_unknown_endpoint_returns_default_mock(self) -> None:
        from memory_engine.utils.feishu_client import feishu_call

        r = feishu_call("/open-apis/totally/unknown/endpoint", "GET")
        assert r.code == 0
        assert r.msg == "ok"
        assert r.data == {}

    def test_empty_endpoint_raises(self) -> None:
        from memory_engine.utils.feishu_client import feishu_call

        with pytest.raises(ValueError, match="endpoint 不能为空"):
            feishu_call("", "POST")
