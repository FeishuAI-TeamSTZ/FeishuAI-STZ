"""配置常量 + 运行时 ``Settings``。

来源（04-ENGUIDE §9.2）：所有阈值 / 权重 / 预算的**单点定义**——M1–M7 业务模块只能从此处 import，
不允许散落 magic number。

约束镜像（宪法 §4.4 / §5.5 / 02-DESIGN）：
- ``DAILY_LLM_BUDGET`` 镜像 §4.4 表，总和 ≤ 10K calls/day
- ``CONSENSUS_WEIGHTS`` 中 OKR 必须最高（**W9** 不变量）
- ``DEFAULT_DAILY_CARD_QUOTA = 5``（**W14** 默认上限）
- ``WORK_HOUR_*_DEFAULT = 9 / 19``（**W15** 默认工作窗）
"""

from __future__ import annotations

from typing import Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .exceptions import ConfigError
from .types import LLMCategory, Provenance, SourceType

# ============================================================
# 信任权重（M4 Actor-Aware 六档）
# ============================================================

PROVENANCE_TRUST_WEIGHTS: Final[dict[Provenance, float]] = {
    Provenance.USER_STATED: 1.00,
    Provenance.OKR_SYNCED: 0.95,
    Provenance.APPROVAL_PASSED: 0.90,
    Provenance.DOC_SYNCED: 0.85,
    Provenance.MEETING_EXTRACTED: 0.70,
    Provenance.SYSTEM_INFERRED: 0.50,
}

# ============================================================
# 跨源共识权重（M1 一致性检测；W9: OKR 顶档不可让位）
# ============================================================

CONSENSUS_WEIGHTS: Final[dict[SourceType, float]] = {
    SourceType.OKR: 0.40,
    SourceType.DOC: 0.30,
    SourceType.MESSAGE: 0.20,
    SourceType.CALENDAR: 0.05,
    SourceType.APPROVAL: 0.05,
}

# ============================================================
# LLM 日预算（calls/day；TPM 1w 派生约 10K calls/day，宪法 §4.4）
# ============================================================

DAILY_LLM_BUDGET: Final[dict[LLMCategory, int]] = {
    LLMCategory.EXTRACT_LIGHT: 3000,
    LLMCategory.EVOLVE_HEAVY: 3000,
    LLMCategory.REFLECT_BORDER: 1500,
    LLMCategory.CROSS_ALIGN: 1500,
    LLMCategory.DECAY_OFFLINE: 500,
}

# ============================================================
# 阈值（02-DESIGN §四 各机制）
# ============================================================

UNCERTAINTY_CARD_THRESHOLD: Final[float] = 0.7  # 机制六：SOFT 高不确定推卡阈值
REFLECT_CONFIDENCE_LOW: Final[float] = 0.5  # 机制三：边界判定下界
REFLECT_CONFIDENCE_HIGH: Final[float] = 0.85  # 机制三：边界判定上界
ACTIVE_CONFIDENCE_MIN: Final[float] = 0.85  # 状态机：state=ACTIVE 入口下界

# ============================================================
# 闸门（W14 / W15）
# ============================================================

DEFAULT_DAILY_CARD_QUOTA: Final[int] = 5  # W14
WORK_HOUR_START_DEFAULT: Final[int] = 9  # W15
WORK_HOUR_END_DEFAULT: Final[int] = 19  # W15

# ============================================================
# 衰减（M7）
# ============================================================

DECAY_LAMBDA_BASE: Final[float] = 0.05  # 待 06-benchmark 校准
DECAY_BATCH_INTERVAL_SECONDS: Final[int] = 60  # APScheduler 批次周期

# ============================================================
# 缓存（W7：5 min 最终一致）
# ============================================================

HOT_PATH_CACHE_TTL_SECONDS: Final[int] = 300


# ============================================================
# 运行时 Settings（pydantic-settings）
# ============================================================


class Settings(BaseSettings):
    """从 ``.env`` 加载的运行时配置（04-ENGUIDE §9.1 镜像）。

    ``ConfigError`` 在 :func:`get_settings` 包装 pydantic ``ValidationError``，
    使应用层只见自定义异常树（CLAUDE.md §2.7 + 04-ENGUIDE §8.11）。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 必填
    database_url: str = Field(min_length=1)
    doubao_api_key: str = Field(min_length=1)
    feishu_app_id: str = Field(min_length=1)
    feishu_app_secret: str = Field(min_length=1)
    feishu_verification_token: str = Field(min_length=1)

    # 选填（开发期可空，生产期由部署校验）
    doubao_heavy_endpoint_id: str = ""
    doubao_light_endpoint_id: str = ""
    doubao_embedding_endpoint_id: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    llm_tpm_tier: str = "single"  # single | group
    feishu_encrypt_key: str = ""

    log_level: str = "INFO"
    environment: str = "development"

    cache_backend: str = "memory"  # memory | redis
    redis_url: str = ""


def get_settings() -> Settings:
    """读 ``.env`` 实例化 :class:`Settings`；缺必填字段抛 :class:`ConfigError`。

    单测用 ``monkeypatch.setenv`` 注入；CI 默认 ``.env`` 不存在仍会读环境变量。
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        raise ConfigError(extra={"reason": str(exc)}) from exc


__all__ = [
    "PROVENANCE_TRUST_WEIGHTS",
    "CONSENSUS_WEIGHTS",
    "DAILY_LLM_BUDGET",
    "UNCERTAINTY_CARD_THRESHOLD",
    "REFLECT_CONFIDENCE_LOW",
    "REFLECT_CONFIDENCE_HIGH",
    "ACTIVE_CONFIDENCE_MIN",
    "DEFAULT_DAILY_CARD_QUOTA",
    "WORK_HOUR_START_DEFAULT",
    "WORK_HOUR_END_DEFAULT",
    "DECAY_LAMBDA_BASE",
    "DECAY_BATCH_INTERVAL_SECONDS",
    "HOT_PATH_CACHE_TTL_SECONDS",
    "Settings",
    "get_settings",
]
