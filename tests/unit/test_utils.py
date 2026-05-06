"""T-005 P0 单测：cache + invariants（W2 / W14 / W15）。

覆盖：
- Cache：miss / set+get / TTL 默认值 / glob invalidate / clear / size
- W2：SUPERSEDES 父必须 ARCHIVED；REFINES 父必须保 ACTIVE；ROOT 跳过
- W14：current_count < max → OK；>= max → W14Violation
- W15：本地工时内 OK；时区外 → W15Violation
- 异常携带 trace_id + extra（structlog 关联用）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from memory_engine.exceptions import W2Violation, W14Violation, W15Violation
from memory_engine.types import DecisionState, EvolutionType
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
