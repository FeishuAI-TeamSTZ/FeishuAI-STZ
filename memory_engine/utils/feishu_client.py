"""飞书 API 调用唯一入口（W13 强制层）。

T-005 P2 D27：mock-first
- ``USE_FEISHU_MOCK=1``（dev 默认）：返回 fixture-style ``FeishuResponse(code=0, ...)``
- ``USE_FEISHU_MOCK=0``（prod）：httpx POST 到 ``feishu_base_url`` + endpoint

W13 不变量（[03-SCHEMA §9](../../docs/03-SCHEMA.md)）：
所有飞书 API 调用必须生成 ``trace_id`` 并 INSERT 到 ``trace_log`` 表。
当前实现：trace_id 必生成 + structlog 记录；**真 DB INSERT 留 T-006**（业务 cold_path
注入 DB session 时统一接入）。这与 W13 在 DB 层的 NOT NULL PK CHECK 互补——只要进
DB 路径就绕不过；mock 模式不进 DB 路径，trace_id 仅作日志关联用。

签名对齐 [04-ENGUIDE §5.2 §8.9](../../docs/04-ENGUIDE.md):
``feishu_call(endpoint, method, payload, *, direction) -> FeishuResponse``
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Literal, cast

import httpx

from memory_engine.config import get_settings
from memory_engine.exceptions import (
    FeishuAPIError,
    FeishuRateLimitError,
)
from memory_engine.types import FeishuResponse

_log = logging.getLogger(__name__)


def _is_mock_mode() -> bool:
    """``USE_FEISHU_MOCK`` 默认 "1"（mock）；显式 "0" 走真路径。"""
    return os.environ.get("USE_FEISHU_MOCK", "1") != "0"


def _new_trace_id() -> str:
    """生成 trace_id：``trc_<16 字符 hex>``，比 LLM trace_id 长以区分。"""
    return f"trc_{uuid.uuid4().hex[:16]}"


# ============================================================
# §1. Mock 实现（fixture-style 响应）
# ============================================================

# 按 endpoint 前缀分组的 mock 响应模板（按需扩展）
_MOCK_TEMPLATES: dict[str, dict[str, Any]] = {
    "/open-apis/auth/v3/tenant_access_token/internal": {
        "code": 0,
        "msg": "ok",
        "tenant_access_token": "t-mock-token",
        "expire": 7200,
    },
    "/open-apis/im/v1/messages": {
        "code": 0,
        "msg": "ok",
        "data": {"message_id": "om_mock_msg_id"},
    },
    "/open-apis/contact/v3/users/": {
        "code": 0,
        "msg": "ok",
        "data": {"user": {"name": "mock_user", "open_id": "ou_mock_id"}},
    },
}


def _mock_response(endpoint: str, trace_id: str) -> FeishuResponse:
    """按 endpoint 前缀匹配 mock 模板；未命中返回通用 ``code=0, data={}``。"""
    template: dict[str, Any] | None = None
    for prefix, tpl in _MOCK_TEMPLATES.items():
        if endpoint.startswith(prefix):
            template = tpl
            break
    if template is None:
        template = {"code": 0, "msg": "ok", "data": {}}
    return FeishuResponse(
        code=int(template.get("code", 0)),
        msg=str(template.get("msg", "ok")),
        data=cast(dict[str, Any], template.get("data", template)),
        trace_id=trace_id,
        latency_ms=1,
    )


# ============================================================
# §2. 真调实现（httpx 同步；best-effort，未真接入测试）
# ============================================================


def _real_call(
    endpoint: str,
    method: Literal["GET", "POST", "PUT", "DELETE"],
    payload: dict[str, Any] | None,
    trace_id: str,
) -> FeishuResponse:
    """真调飞书开放平台（best-effort；未真接入测试）。"""
    settings = get_settings()
    url = f"https://open.feishu.cn{endpoint}"
    headers = {"Content-Type": "application/json; charset=utf-8"}

    started = time.time()
    try:
        if method == "GET":
            response = httpx.get(url, headers=headers, params=payload, timeout=10.0)
        else:
            response = httpx.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=10.0,
            )
    except httpx.TimeoutException as e:
        raise FeishuAPIError(
            trace_id=trace_id,
            extra={"endpoint": endpoint, "reason": "timeout"},
        ) from e
    except httpx.HTTPError as e:
        raise FeishuAPIError(
            trace_id=trace_id,
            extra={"endpoint": endpoint, "http_error": str(e)},
        ) from e

    if response.status_code == 429:
        raise FeishuRateLimitError(
            trace_id=trace_id,
            extra={"endpoint": endpoint, "retry_after": response.headers.get("Retry-After")},
        )

    try:
        data = cast(dict[str, Any], response.json())
    except ValueError as e:
        raise FeishuAPIError(
            trace_id=trace_id,
            extra={"endpoint": endpoint, "parse_error": str(e)},
        ) from e

    latency_ms = int((time.time() - started) * 1000)
    return FeishuResponse(
        code=int(data.get("code", -1)),
        msg=str(data.get("msg", "")),
        data=cast(dict[str, Any], data.get("data", {})),
        trace_id=trace_id,
        latency_ms=latency_ms,
    )


# ============================================================
# §3. 公开 API（W13 强制：trace_id 必生成）
# ============================================================


def feishu_call(
    endpoint: str,
    method: Literal["GET", "POST", "PUT", "DELETE"] = "POST",
    payload: dict[str, Any] | None = None,
    *,
    direction: Literal["OUT", "IN", "HOOK"] = "OUT",
) -> FeishuResponse:
    """飞书 API 调用唯一入口；自动生成 trace_id 并 structlog 记录。

    :param endpoint:  飞书 API 路径（如 ``/open-apis/im/v1/messages``）
    :param method:    HTTP 动词
    :param payload:   GET 用作 query params；其他用作 JSON body
    :param direction: ``OUT`` = 我们 → 飞书（默认）；``IN`` = 飞书 → 我们；``HOOK`` = webhook
    :return:          ``FeishuResponse``，含 trace_id

    W13 注：``trace_id`` 100% 生成；真路径下 T-006 业务层将注入 DB session
    把 trace_log INSERT 落库；mock 模式仅日志记录（不进 DB 路径）。
    """
    if not endpoint:
        raise ValueError("endpoint 不能为空")

    trace_id = _new_trace_id()
    _log.info(
        "feishu_call_start",
        extra={
            "trace_id": trace_id,
            "endpoint": endpoint,
            "method": method,
            "direction": direction,
            "mock": _is_mock_mode(),
        },
    )

    if _is_mock_mode():
        resp = _mock_response(endpoint, trace_id)
    else:
        resp = _real_call(endpoint, method, payload, trace_id)

    _log.info(
        "feishu_call_end",
        extra={
            "trace_id": trace_id,
            "endpoint": endpoint,
            "code": resp.code,
            "latency_ms": resp.latency_ms,
        },
    )
    return resp


__all__ = [
    "feishu_call",
]
