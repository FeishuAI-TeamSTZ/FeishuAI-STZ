"""Hot Path 进程内缓存（cachetools.TTLCache 5 min；v1）。

T-005 P0：cachetools `TTLCache`，单进程内存。
v2 切 Redis 由 ``CACHE_BACKEND=redis`` env 触发（宪法 §3.3 / 04-ENGUIDE §8.9）。

签名对齐 [04-ENGUIDE §8.9](../docs/04-ENGUIDE.md#cache)：
- ``cache_get(key)``
- ``cache_set(key, value, ttl_seconds=300)``
- ``cache_invalidate(pattern)``  glob 模式

关于 per-key TTL：``cachetools.TTLCache`` 不支持 per-key TTL，所有 key 用 cache 实例
配置的 ``HOT_PATH_CACHE_TTL_SECONDS = 300``；``ttl_seconds`` 参数当前**忽略**（保留签名
为未来 Redis 后端扩展）。
"""

from __future__ import annotations

import fnmatch
from threading import RLock
from typing import Any, cast

from cachetools import TTLCache

from memory_engine.config import HOT_PATH_CACHE_TTL_SECONDS

# ---------------------------------------------------------------- Cache 实例

_DEFAULT_MAX_SIZE = 10_000

_cache: TTLCache[str, Any] = TTLCache(
    maxsize=_DEFAULT_MAX_SIZE,
    ttl=HOT_PATH_CACHE_TTL_SECONDS,
)
_lock = RLock()


# ---------------------------------------------------------------- 公开 API

def cache_get(key: str) -> Any | None:
    """读 key；命中返回值，未命中或过期返回 ``None``。"""
    with _lock:
        return cast(Any, _cache.get(key))


def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    """写 key（默认 TTL = ``HOT_PATH_CACHE_TTL_SECONDS``）。

    :param key:         缓存键
    :param value:       任意可序列化值（v1 不强制；v2 切 Redis 时再约束）
    :param ttl_seconds: **当前忽略**（cachetools 单 cache 实例统一 TTL）；签名保留
                         供 v2 Redis 后端按 key 设 TTL 用
    """
    _ = ttl_seconds  # 显式标记忽略（避免 ruff 未使用参数警告）
    with _lock:
        _cache[key] = value


def cache_invalidate(pattern: str) -> int:
    """按 glob 模式批量失效；返回失效条数。

    示例：``cache_invalidate('dec_*')`` 失效所有 ``dec_`` 前缀键。
    """
    with _lock:
        matched = [k for k in list(_cache.keys()) if fnmatch.fnmatch(k, pattern)]
        for k in matched:
            del _cache[k]
        return len(matched)


def cache_clear() -> None:
    """清空整个缓存（仅测试或失效全局策略时用）。"""
    with _lock:
        _cache.clear()


def cache_size() -> int:
    """当前活跃 key 数（已过期的不计；cachetools 自动剔除）。"""
    with _lock:
        return len(_cache)


__all__ = [
    "cache_get",
    "cache_set",
    "cache_invalidate",
    "cache_clear",
    "cache_size",
]
