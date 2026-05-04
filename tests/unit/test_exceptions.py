"""异常树冒烟测试。

校验：
- 所有 25 个异常类可 instantiate（trace_id + extra）
- ``__str__`` 输出含 trace_id 与类名
- 继承关系正确（W2Violation < InvariantViolation < MemoryEngineError）
"""

from __future__ import annotations

import pytest

from memory_engine.exceptions import (
    ConfigError,
    DBConsistencyError,
    DBError,
    DBQueryError,
    ExtractionError,
    ExtractionTimeoutError,
    FeishuAPIError,
    FeishuError,
    FeishuRateLimitError,
    FeishuTraceLogError,
    InvalidDecisionAtomError,
    InvariantViolation,
    LLMError,
    LLMQuotaExceededError,
    LLMResponseInvalidError,
    LLMTimeoutError,
    MemoryEngineError,
    W2Violation,
    W13Violation,
    W14Violation,
)

ALL_EXCEPTION_CLASSES = [
    MemoryEngineError,
    LLMError,
    LLMQuotaExceededError,
    LLMTimeoutError,
    LLMResponseInvalidError,
    FeishuError,
    FeishuAPIError,
    FeishuTraceLogError,
    FeishuRateLimitError,
    DBError,
    DBQueryError,
    DBConsistencyError,
    InvariantViolation,
    W2Violation,
    W13Violation,
    W14Violation,
    ExtractionError,
    ExtractionTimeoutError,
    InvalidDecisionAtomError,
    ConfigError,
]


@pytest.mark.parametrize("cls", ALL_EXCEPTION_CLASSES)
def test_exception_can_instantiate(cls: type[MemoryEngineError]) -> None:
    """每个异常类都能用 trace_id + extra 构造。"""
    err = cls(trace_id="trc_t1", extra={"key": "value"})
    assert err.trace_id == "trc_t1"
    assert err.extra == {"key": "value"}


def test_str_contains_trace_id_and_class_name() -> None:
    """``__str__`` 输出含类名 + trace= + extra。"""
    err = LLMQuotaExceededError(trace_id="trc_abc", extra={"category": "EVOLVE_HEAVY"})
    s = str(err)
    assert "LLMQuotaExceededError" in s
    assert "trace=trc_abc" in s
    assert "EVOLVE_HEAVY" in s


def test_str_without_extra() -> None:
    """无 extra 时 ``__str__`` 不带尾随 dict。"""
    err = MemoryEngineError(trace_id="trc_x")
    assert str(err) == "[MemoryEngineError trace=trc_x]"


def test_default_trace_id_empty() -> None:
    """缺省 trace_id 是空串（兼容尚未接入 W13 trace 的边界）。"""
    err = ConfigError()
    assert err.trace_id == ""
    assert err.extra == {}


def test_invariant_hierarchy() -> None:
    """W*Violation 全部 isinstance InvariantViolation 与 MemoryEngineError。"""
    for cls in (W2Violation, W13Violation, W14Violation):
        err = cls(trace_id="t")
        assert isinstance(err, InvariantViolation)
        assert isinstance(err, MemoryEngineError)


def test_llm_subclass_hierarchy() -> None:
    """LLMQuotaExceeded < LLMError < MemoryEngineError。"""
    err = LLMQuotaExceededError(trace_id="t")
    assert isinstance(err, LLMError)
    assert isinstance(err, MemoryEngineError)


def test_feishu_subclass_hierarchy() -> None:
    """FeishuTraceLogError < FeishuError < MemoryEngineError。"""
    err = FeishuTraceLogError(trace_id="t")
    assert isinstance(err, FeishuError)
    assert isinstance(err, MemoryEngineError)
