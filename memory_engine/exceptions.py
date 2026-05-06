"""自定义异常树。

对齐 04-ENGUIDE §8.11 异常体系图。

纪律：
- 业务代码不允许 ``raise Exception(...)``，必须用本模块定义的类
- 所有 :class:`MemoryEngineError` 子类**必须**有 ``trace_id`` 属性（便于日志关联）
- 不允许把异常吞掉（必须 re-raise 或转换为更高层异常）
"""

from __future__ import annotations

from typing import Any


class MemoryEngineError(Exception):
    """根异常类。所有自定义异常的祖先。

    所有子类共享 ``trace_id`` 与 ``extra`` 两个属性：

    - ``trace_id``: 飞书 / LLM 调用绑定的 trace ID（W13 强制层产生）
    - ``extra``: 任意结构化上下文（如 decision_id / user_id / category）
    """

    def __init__(
        self,
        *,
        trace_id: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.extra = extra or {}
        super().__init__(self.__str__())

    def __str__(self) -> str:
        cls = type(self).__name__
        if self.extra:
            return f"[{cls} trace={self.trace_id}] {self.extra}"
        return f"[{cls} trace={self.trace_id}]"


# ---------------------------------------------------------------- LLM
class LLMError(MemoryEngineError):
    """LLM 网关相关错误的基类。"""


class LLMQuotaExceededError(LLMError):
    """W12 触发降级：日额度耗尽（按 :class:`LLMCategory` 分类）。"""


class LLMTimeoutError(LLMError):
    """LLM 调用超时（light=5s / heavy=15s / embedding=3s）。"""


class LLMResponseInvalidError(LLMError):
    """LLM 返回 JSON 解析失败 / 必需字段缺失。"""


# ---------------------------------------------------------------- Feishu
class FeishuError(MemoryEngineError):
    """飞书 API 相关错误的基类。"""


class FeishuAPIError(FeishuError):
    """飞书 API 4xx / 5xx 持久失败（重试用尽后抛）。"""


class FeishuTraceLogError(FeishuError):
    """W13 强制：trace_log INSERT 失败时抛出，request 不发出。"""


class FeishuRateLimitError(FeishuError):
    """飞书 429 但已重试用尽（Retry-After 后仍 429）。"""


# ---------------------------------------------------------------- DB
class DBError(MemoryEngineError):
    """数据库相关错误的基类。"""


class DBQueryError(DBError):
    """SELECT / DML 失败。"""


class DBConsistencyError(DBError):
    """schema.sql 与 models.py 漂移；validate_consistency.py 报告（T-003 启用）。"""


# ---------------------------------------------------------------- Invariants
class InvariantViolation(MemoryEngineError):
    """W1–W15 任一违反。"""


class W2Violation(InvariantViolation):
    """W2: REFINES 父保 ACTIVE / SUPERSEDES 父转 ARCHIVED 在数据上未成立。"""


class W13Violation(InvariantViolation):
    """W13: 飞书 API 调用未记录 trace_id。"""


class W14Violation(InvariantViolation):
    """W14: 单用户每日卡片推送超过 max_daily。"""


class W15Violation(InvariantViolation):
    """W15: 非工作时段推送非紧急卡片（用户本地时区 work_hour 窗外）。"""


# ---------------------------------------------------------------- Extraction
class ExtractionError(MemoryEngineError):
    """决策原子提取阶段错误的基类。"""


class ExtractionTimeoutError(ExtractionError):
    """单条消息提取超过 5s（M1 super timeout）。"""


class InvalidDecisionAtomError(ExtractionError):
    """提取后的 DecisionAtom 七字段不完整或不合法。"""


# ---------------------------------------------------------------- Config
class ConfigError(MemoryEngineError):
    """配置错误（环境变量缺失 / 类型不对 / 取值越界）。"""
