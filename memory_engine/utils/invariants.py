"""W1–W15 不变量运行时检查（DB CHECK 约束的 App 层双保险）。

T-005 P0：纯函数实现（不连 DB）；调用方负责 fetch 必要状态后传入。
对应规约：[04-ENGUIDE §8.9](../docs/04-ENGUIDE.md) + [03-SCHEMA §9](../docs/03-SCHEMA.md)。

设计原则（T-002 D5：W2 应用层 + 巡检双保险）：
- W2 / W13 / W14 均在 DB 层 CHECK 强制（schema.sql）；本模块在 App 端再次 assert
- W15 仅在 App 层强制（DB 不知用户时区与工作时段语义）
- 任一 assert 失败 raise 具体 ``InvariantViolation`` 子类，含 ``trace_id`` + ``extra``
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from memory_engine.config import DEFAULT_DAILY_CARD_QUOTA
from memory_engine.exceptions import (
    W2Violation,
    W14Violation,
    W15Violation,
)
from memory_engine.types import DecisionState, EvolutionType


# ---------------------------------------------------------------- W2

def assert_w2(
    parent_state: DecisionState,
    edge_type: EvolutionType,
    *,
    trace_id: str = "",
) -> None:
    """W2：REFINES 父保 ACTIVE / SUPERSEDES 父转 ARCHIVED。

    :param parent_state: SUPERSEDES 边创建后父决策的当前 ``state``
    :param edge_type:    演化关系类型
    :raises W2Violation: 父决策 state 与 edge_type 语义不一致

    SUPERSEDES：父必须已是 ARCHIVED（应用层在 commit_evolution 后立即 transition）
    REFINES / GENERALIZES / BRANCHES：父必须保 ACTIVE（被覆盖会破坏 W2）
    ROOT：无父，跳过检查（调用方应该不传 ROOT）
    """
    if edge_type == EvolutionType.ROOT:
        return  # ROOT 无父，无需检查

    if edge_type == EvolutionType.SUPERSEDES:
        if parent_state != DecisionState.ARCHIVED:
            raise W2Violation(
                trace_id=trace_id,
                extra={
                    "edge_type": edge_type.value,
                    "parent_state": parent_state.value,
                    "expected": DecisionState.ARCHIVED.value,
                    "rule": "SUPERSEDES 后父决策必须 ARCHIVED",
                },
            )
        return

    # REFINES / GENERALIZES / BRANCHES：父保 ACTIVE
    if parent_state == DecisionState.ARCHIVED:
        raise W2Violation(
            trace_id=trace_id,
            extra={
                "edge_type": edge_type.value,
                "parent_state": parent_state.value,
                "expected_not": DecisionState.ARCHIVED.value,
                "rule": f"{edge_type.value} 不应导致父决策 ARCHIVED",
            },
        )


# ---------------------------------------------------------------- W14

def assert_w14(
    current_count: int,
    *,
    max_daily: int = DEFAULT_DAILY_CARD_QUOTA,
    user_id: str = "",
    trace_id: str = "",
) -> None:
    """W14：单用户每日卡片推送 ≤ max_daily（DB CHECK 双保险）。

    调用方负责从 ``card_quota`` 表查到当日 ``count`` 并传入。
    本函数不连 DB，纯逻辑断言。

    :param current_count: 当日已推送数（在打算推下一张卡前调）
    :param max_daily:     上限（默认 ``DEFAULT_DAILY_CARD_QUOTA = 5``）
    :raises W14Violation: 即将超额（current_count >= max_daily）
    """
    if current_count >= max_daily:
        raise W14Violation(
            trace_id=trace_id,
            extra={
                "user_id": user_id,
                "current_count": current_count,
                "max_daily": max_daily,
                "rule": f"已推送 {current_count} 张，上限 {max_daily}",
            },
        )


# ---------------------------------------------------------------- W15

def assert_w15(
    now: datetime,
    *,
    work_hour_start: int,
    work_hour_end: int,
    timezone_str: str = "Asia/Shanghai",
    user_id: str = "",
    trace_id: str = "",
) -> None:
    """W15：非工作时段（用户本地时区）暂停非紧急卡片推送。

    HARD 拦截（CLI 失败拦截等紧急场景）不应过本函数；只对 SOFT_INQUIRY / GHOST_LOG /
    EVOLUTION_NOTICE 三类调用。

    :param now:               当前 UTC（aware）时间
    :param work_hour_start:   用户本地时区工作起始小时（0–23）
    :param work_hour_end:     用户本地时区工作结束小时（1–24，> work_hour_start）
    :param timezone_str:      IANA 时区名（默认 Asia/Shanghai）
    :raises W15Violation:     当前不在工作时段
    """
    local = now.astimezone(ZoneInfo(timezone_str))
    local_hour = local.hour
    if not (work_hour_start <= local_hour < work_hour_end):
        raise W15Violation(
            trace_id=trace_id,
            extra={
                "user_id": user_id,
                "local_hour": local_hour,
                "timezone": timezone_str,
                "work_hour_start": work_hour_start,
                "work_hour_end": work_hour_end,
                "rule": f"当前 {local_hour}:00 不在 [{work_hour_start}, {work_hour_end}) 内",
            },
        )


__all__ = [
    "assert_w2",
    "assert_w14",
    "assert_w15",
]
