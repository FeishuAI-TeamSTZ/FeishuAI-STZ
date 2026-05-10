"""LLM 调用唯一入口（CLAUDE.md §2.5 强制）；Doubao 三档 + W12 降级 + TPM 计数。

T-005 P1 D25：mock-first
- ``USE_LLM_MOCK=1``（dev 默认）：返回 deterministic JSON（按 ``LLMCategory`` 模板）
- ``USE_LLM_MOCK=0``（prod）：httpx POST 到 Doubao Heavy / Light EP

签名对齐 [04-ENGUIDE §4.2 §8.9](../docs/04-ENGUIDE.md)：
- ``light_llm_extract(prompt, max_tokens=500, *, category) -> LLMResponse``  ← Doubao 1.6
- ``heavy_llm_extract(prompt, max_tokens=2000, *, category) -> LLMResponse`` ← Doubao 2.0

W12 降级：日 token 预算（``DAILY_LLM_BUDGET[category]``）耗尽 raise
``LLMQuotaExceededError``；当前实现仅做 budget 计数，本地 7B 切换是 v1.1 路径
（v1 不接入本地模型）。
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from threading import RLock
from typing import Any, cast

import httpx

from memory_engine.config import DAILY_LLM_BUDGET, get_settings
from memory_engine.exceptions import (
    LLMQuotaExceededError,
    LLMResponseInvalidError,
    LLMTimeoutError,
)
from memory_engine.types import LLMCategory, LLMResponse


def _is_mock_mode() -> bool:
    """``USE_LLM_MOCK`` 默认 "1"（mock）；显式 "0" 走真路径。"""
    return os.environ.get("USE_LLM_MOCK", "1") != "0"


# ============================================================
# §1. 日 token 预算计数器（线程安全）
# ============================================================

_quota_used: dict[LLMCategory, int] = dict.fromkeys(LLMCategory, 0)
_quota_lock = RLock()


def _check_and_consume_quota(category: LLMCategory, tokens: int) -> None:
    """W12 budget enforcement：扣减预算；若超限 raise。"""
    with _quota_lock:
        used = _quota_used[category]
        budget = DAILY_LLM_BUDGET.get(category, 0)
        if used + tokens > budget:
            raise LLMQuotaExceededError(
                extra={
                    "category": category.value,
                    "used": used,
                    "requested": tokens,
                    "budget": budget,
                }
            )
        _quota_used[category] = used + tokens


def _reset_quota() -> None:
    """单测用：重置所有 category 的累计 token。"""
    with _quota_lock:
        for cat in LLMCategory:
            _quota_used[cat] = 0


def _get_quota_used(category: LLMCategory) -> int:
    with _quota_lock:
        return _quota_used[category]


# ============================================================
# §2. Mock 实现（deterministic JSON 模板）
# ============================================================

_MOCK_TEMPLATES: dict[LLMCategory, str] = {
    LLMCategory.EXTRACT_LIGHT: (
        '{"subject": "项目A", "predicate": "RELEASE_DATE", '
        '"object": "2026-05-15", "confidence": 0.85, '
        '"provenance": "USER_STATED"}'
    ),
    LLMCategory.EVOLVE_HEAVY: (
        '{"evolution_type": "ROOT", "confidence": 0.95, '
        '"reasoning": "mock - 新决策原子，无父节点"}'
    ),
    LLMCategory.REFLECT_BORDER: (
        '{"quality_score": 0.85, "potential_missed_parent_id": null, '
        '"suggested_type": null, "confidence_calibration": 0.0, '
        '"reasoning": "mock - 判定合理"}'
    ),
    LLMCategory.CROSS_ALIGN: (
        '{"alignment": "ALIGNED", "similarity": 0.9, '
        '"reasoning": "mock - 跨源语义一致"}'
    ),
    LLMCategory.DECAY_OFFLINE: (
        '{"f_freq": 0.5, "f_consensus": 0.5, "f_semantic": 0.5, '
        '"f_uncertainty": 0.5, "f_user_validation": 0.5}'
    ),
}


def _mock_response(prompt: str, category: LLMCategory, trace_id: str) -> LLMResponse:
    """deterministic mock：模板 + prompt 长度 token 估算。"""
    content = _MOCK_TEMPLATES.get(
        category,
        f'{{"mock": true, "category": "{category.value}"}}',
    )
    # token 估算：prompt 字符数 / 2 + content 字符数 / 2（粗略经验值）
    tokens = (len(prompt) + len(content)) // 2 + 50
    return LLMResponse(
        content=content,
        tokens_used=tokens,
        used_local=False,
        trace_id=trace_id,
        latency_ms=1,  # mock 即时返回
    )


# ============================================================
# §3. 真调实现（httpx 同步；best-effort，未实测）
# ============================================================

_TIMEOUTS: dict[str, float] = {"light": 5.0, "heavy": 15.0}


def _real_call(
    prompt: str,
    max_tokens: int,
    category: LLMCategory,
    trace_id: str,
    *,
    is_heavy: bool,
) -> LLMResponse:
    """真调 Doubao（best-effort；未真接入测试）；lazy load Settings（mock 模式不触发）。"""
    settings = get_settings()
    endpoint_id = (
        settings.doubao_heavy_endpoint_id if is_heavy else settings.doubao_light_endpoint_id
    )
    if not endpoint_id:
        raise LLMResponseInvalidError(
            trace_id=trace_id,
            extra={"reason": f"DOUBAO_{'HEAVY' if is_heavy else 'LIGHT'}_ENDPOINT_ID 未配置"},
        )

    started = time.time()
    timeout = _TIMEOUTS["heavy" if is_heavy else "light"]
    try:
        response = httpx.post(
            f"{settings.doubao_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.doubao_api_key}"},
            json={
                "model": endpoint_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(
            trace_id=trace_id,
            extra={"category": category.value, "timeout_s": timeout},
        ) from e
    except httpx.HTTPError as e:
        raise LLMResponseInvalidError(
            trace_id=trace_id,
            extra={"category": category.value, "http_error": str(e)},
        ) from e

    try:
        data = cast(dict[str, Any], response.json())
        content = cast(str, data["choices"][0]["message"]["content"])
        tokens_used = cast(int, data.get("usage", {}).get("total_tokens", 0))
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMResponseInvalidError(
            trace_id=trace_id,
            extra={"category": category.value, "parse_error": str(e)},
        ) from e

    latency_ms = int((time.time() - started) * 1000)
    return LLMResponse(
        content=content,
        tokens_used=tokens_used,
        used_local=False,
        trace_id=trace_id,
        latency_ms=latency_ms,
    )


# ============================================================
# §4. 公开 API
# ============================================================

def _new_trace_id() -> str:
    """生成 trace_id：``trc_<8 字符 hex>``，便于日志关联。"""
    return f"trc_{uuid.uuid4().hex[:8]}"


def _stable_trace_id(prompt: str, category: LLMCategory) -> str:
    """mock 模式 deterministic trace_id：(prompt, category) → 同 trace_id（便于单测）。"""
    seed = f"{category.value}|{prompt}".encode("utf-8")
    return f"trc_{hashlib.sha256(seed).hexdigest()[:8]}"


def light_llm_extract(
    prompt: str,
    max_tokens: int = 500,
    *,
    category: LLMCategory,
) -> LLMResponse:
    """Light LLM 调用（Doubao 1.6）：决策原子提取 / 离线参数校准。"""
    if not prompt:
        raise ValueError("prompt 不能为空")

    if _is_mock_mode():
        trace_id = _stable_trace_id(prompt, category)
        resp = _mock_response(prompt, category, trace_id)
        _check_and_consume_quota(category, resp.tokens_used)
        return resp

    trace_id = _new_trace_id()
    resp = _real_call(prompt, max_tokens, category, trace_id, is_heavy=False)
    _check_and_consume_quota(category, resp.tokens_used)
    return resp


def heavy_llm_extract(
    prompt: str,
    max_tokens: int = 2000,
    *,
    category: LLMCategory,
) -> LLMResponse:
    """Heavy LLM 调用（Doubao 2.0）：演化判定 / Reflect / 跨源对齐。"""
    if not prompt:
        raise ValueError("prompt 不能为空")

    if _is_mock_mode():
        trace_id = _stable_trace_id(prompt, category)
        resp = _mock_response(prompt, category, trace_id)
        _check_and_consume_quota(category, resp.tokens_used)
        return resp

    trace_id = _new_trace_id()
    resp = _real_call(prompt, max_tokens, category, trace_id, is_heavy=True)
    _check_and_consume_quota(category, resp.tokens_used)
    return resp


__all__ = [
    "light_llm_extract",
    "heavy_llm_extract",
    # 单测辅助
    "_reset_quota",
    "_get_quota_used",
]
