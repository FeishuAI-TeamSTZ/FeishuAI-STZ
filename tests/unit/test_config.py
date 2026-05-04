"""配置常量 + Settings 自检。

W9 / 5 因子 / 总预算上限 / Settings fail-fast 在此一处验。
"""

from __future__ import annotations

import pytest

from memory_engine.config import (
    ACTIVE_CONFIDENCE_MIN,
    CONSENSUS_WEIGHTS,
    DAILY_LLM_BUDGET,
    DECAY_LAMBDA_BASE,
    DEFAULT_DAILY_CARD_QUOTA,
    HOT_PATH_CACHE_TTL_SECONDS,
    PROVENANCE_TRUST_WEIGHTS,
    REFLECT_CONFIDENCE_HIGH,
    REFLECT_CONFIDENCE_LOW,
    UNCERTAINTY_CARD_THRESHOLD,
    WORK_HOUR_END_DEFAULT,
    WORK_HOUR_START_DEFAULT,
    Settings,
    get_settings,
)
from memory_engine.exceptions import ConfigError
from memory_engine.types import LLMCategory, Provenance, SourceType

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+psycopg://memory:memory@localhost:5432/memory",
    "DOUBAO_API_KEY": "test_key",
    "FEISHU_APP_ID": "cli_test",
    "FEISHU_APP_SECRET": "secret_test",
    "FEISHU_VERIFICATION_TOKEN": "token_test",
}


def test_provenance_weights_complete() -> None:
    """6 档 provenance 全部覆盖。"""
    assert set(PROVENANCE_TRUST_WEIGHTS.keys()) == set(Provenance)


def test_provenance_weights_descending() -> None:
    """信任权重严格递减：USER_STATED > OKR > APPROVAL > DOC > MEETING > SYSTEM。"""
    ordered = [
        Provenance.USER_STATED,
        Provenance.OKR_SYNCED,
        Provenance.APPROVAL_PASSED,
        Provenance.DOC_SYNCED,
        Provenance.MEETING_EXTRACTED,
        Provenance.SYSTEM_INFERRED,
    ]
    weights = [PROVENANCE_TRUST_WEIGHTS[p] for p in ordered]
    assert weights == sorted(weights, reverse=True)


def test_w9_okr_top_weight() -> None:
    """**W9** 不变量：OKR 在 CONSENSUS_WEIGHTS 中权重最高。"""
    okr_weight = CONSENSUS_WEIGHTS[SourceType.OKR]
    others = {st: w for st, w in CONSENSUS_WEIGHTS.items() if st is not SourceType.OKR}
    assert all(okr_weight >= w for w in others.values())
    assert okr_weight > max(others.values())  # 严格大于（W9 顶档不可让位）


def test_consensus_weights_sum_one() -> None:
    """跨源权重总和 = 1.0（共识度 C 计算前提）。"""
    assert sum(CONSENSUS_WEIGHTS.values()) == pytest.approx(1.0)


def test_daily_llm_budget_total_within_cap() -> None:
    """**宪法 §4.4** 总日预算 ≤ 10K（TPM 1w 派生）。"""
    total = sum(DAILY_LLM_BUDGET.values())
    assert total <= 10_000


def test_daily_llm_budget_covers_all_categories() -> None:
    """5 类 LLMCategory 全部有预算项。"""
    assert set(DAILY_LLM_BUDGET.keys()) == set(LLMCategory)


def test_thresholds_consistent() -> None:
    """阈值之间满足业务序：LOW < HIGH ≤ ACTIVE_MIN；CARD_THRESHOLD ∈ (0,1)。"""
    assert REFLECT_CONFIDENCE_LOW < REFLECT_CONFIDENCE_HIGH
    assert REFLECT_CONFIDENCE_HIGH <= ACTIVE_CONFIDENCE_MIN
    assert 0 < UNCERTAINTY_CARD_THRESHOLD < 1


def test_w14_default_quota_five() -> None:
    """**W14** 默认 5/日。"""
    assert DEFAULT_DAILY_CARD_QUOTA == 5


def test_w15_work_hours_default() -> None:
    """**W15** 默认 9:00–19:00；start < end 且都在 0–24 范围内。"""
    assert WORK_HOUR_START_DEFAULT == 9
    assert WORK_HOUR_END_DEFAULT == 19
    assert 0 <= WORK_HOUR_START_DEFAULT < WORK_HOUR_END_DEFAULT <= 24


def test_decay_constants_positive() -> None:
    assert DECAY_LAMBDA_BASE > 0
    assert HOT_PATH_CACHE_TTL_SECONDS == 300  # W7: 5 min


def test_settings_loads_when_required_env_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """所有必填环境变量到位时 Settings 实例化成功。"""
    for k, v in REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.database_url == REQUIRED_ENV["DATABASE_URL"]
    assert s.doubao_api_key == "test_key"
    assert s.llm_tpm_tier == "single"  # 默认值
    assert s.cache_backend == "memory"


def test_get_settings_wraps_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺必填字段时 :func:`get_settings` 抛 :class:`ConfigError` 而非 ValidationError。"""
    # 显式清空必填变量；依赖 .env 不存在 / 不被读取
    for k in REQUIRED_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(
        "memory_engine.config.Settings.model_config",
        {**Settings.model_config, "env_file": None},
    )
    with pytest.raises(ConfigError):
        get_settings()
