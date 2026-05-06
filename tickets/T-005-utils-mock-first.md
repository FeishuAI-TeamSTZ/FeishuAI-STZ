# T-005：utils 层（pragmatic mock-first，time-constrained 模式）

> **类型**：Phase 0 收官 ticket（系列 5/5）— 解锁 T-006 M1 切片
> **领地**：R1 内核工程师（`memory_engine/utils/`）
> **优先级**：P0（M1-M7 业务模块全部依赖此层）
> **计划用时**：**6-8 小时**（time-constrained：明天 deadline）
> **关联 §8 接口**：[04-ENGUIDE §8.9 共享工具](../docs/04-ENGUIDE.md)（5 utils 模块完整签名）
> **触及不变量**：W12 LLM 额度耗尽降级 / W13 飞书 trace_log（DB 双保险）/ W15 工作时间窗
> **预算自检**：~510 行 / 5 文件 + 1 测试 = **预算内**（无豁免）
> **依据文档**：[04-ENGUIDE §4 §5 §8.9](../docs/04-ENGUIDE.md)；[01-CONSTITUTION §4.1 §4.4](../docs/01-CONSTITUTION.md)；[02-DESIGN §四 机制四 §四 机制五](../docs/02-DESIGN.md)

---

## 1. 目标（time-constrained）

让以下命令零错误执行：

```bash
# 1) 5 utils 模块可 import
uv run python -c "
from memory_engine.utils import light_llm_extract, heavy_llm_extract
from memory_engine.utils.cache import cache_get, cache_set
from memory_engine.utils.embeddings import compute_embedding
from memory_engine.utils.feishu_client import feishu_call
from memory_engine.utils.invariants import assert_w14, assert_w15
print('OK')
"

# 2) Mock 模式 LLM 调用返回 deterministic JSON
USE_LLM_MOCK=1 uv run python -c "
from memory_engine.utils import heavy_llm_extract
from memory_engine.types import LLMCategory
r = heavy_llm_extract('test', category=LLMCategory.EVOLVE_HEAVY)
print(r.content, r.used_local, r.tokens_used)
# 期望：固定 JSON 字符串 / used_local=False / tokens_used > 0
"

# 3) 缓存 + 嵌入 + 不变量自检
uv run pytest -q tests/unit/test_utils*.py
# 期望：≥ 8 passed

# 4) 既有 73 unit + 5 integration 仍全过
uv run pytest -q
uv run pytest -m integration
```

完成后，**T-006 M1 切片可以直接 `from memory_engine.utils import ...` 开工**；真 Doubao / 飞书集成留 v1.1。

---

## 2. 范围

### 2.1 In Scope（5 文件 + 1 测试 = ~510 行 / 6 文件）

| # | 路径 | 行数 | P | 说明 |
|:---:|:---|:---:|:---:|:---|
| 1 | `memory_engine/utils/invariants.py` | ~80 | P0 | W2/W14/W15 运行时 assert（DB CHECK 双保险）；签名对齐 04-ENGUIDE §8.9 |
| 2 | `memory_engine/utils/cache.py` | ~80 | P0 | cachetools `TTLCache` 5 min；`cache_get` / `cache_set` / `cache_invalidate(pattern)` |
| 3 | `memory_engine/utils/llm_gateway.py` | ~180 | P1 | Doubao 三档（heavy 2.0 / light 1.6 / embedding v1）+ TPM 计数器 + W12 fallback；**`USE_LLM_MOCK=1` env 开关**，dev 默认 mock 返回 deterministic JSON |
| 4 | `memory_engine/utils/embeddings.py` | ~70 | P1 | `compute_embedding(text)` Doubao 1024 维；mock 模式 = `hashlib.sha256` 派生 deterministic 1024 浮点向量；`cosine_similarity` |
| 5 | `memory_engine/utils/feishu_client.py` | ~100 | P2 | `feishu_call(endpoint, method, payload, direction)` + **W13 强制 trace_log INSERT**；mock 模式返回 fixture-style response |
| 6 | `tests/unit/test_utils.py` | ~120 | P0 | 5 模块 smoke + W12/W13/W14 mock 断言；**至少 8 testcase** |

**修订**：
- `memory_engine/utils/__init__.py` — re-export `light_llm_extract` / `heavy_llm_extract` / `compute_embedding`（与 04-ENGUIDE §4.1 一致）
- `.env.example` — 加 `USE_LLM_MOCK=1` + `USE_FEISHU_MOCK=1` 占位

### 2.2 Out of Scope（明确不做）

| 不做 | 归属 |
|:---|:---:|
| 真 Doubao API 集成测试（需真 EP） | T-006 测试期 / v1.1 |
| 真飞书 webhook 接收（需 ngrok 或公网） | T-006 / v1.1 |
| `apscheduler` 任务调度封装 | T-007（v1.1 Phase 1.1 内） |
| 跨进程 Redis 缓存（D6 v2 路径） | v2.x |
| `pgvector` ANN 调优 | benchmark 跑分时 |

### 2.3 D25-D27（time-constrained 新决策）

- **D25**：`USE_LLM_MOCK` env 开关 — dev 默认 `1`（mock）/ prod `0`（真调）；mock 返回 deterministic JSON 解决 T-006 测试期 LLM 不稳定问题
- **D26**：mock embedding 用 `hashlib.sha256(text).digest()` 派生 1024 浮点向量（不真调 Doubao）—— 单测可重复 + 余弦距离仍可比较
- **D27**：`feishu_call` mock 模式从 `tests/fixtures/feishu_responses/` 读 fixture（**T-005 暂不实现该 fixture 目录，T-006 真用到时再补**）；mock 直接返回 `FeishuResponse(code=0, msg="ok", data={}, trace_id="trc_mock", latency_ms=10)`

---

## 3. 关键实现要点

### 3.1 `invariants.py`（最简 ~80 行）

```python
def assert_w2(parent: Decision, child: Decision, edge_type: EvolutionType) -> None:
    """W2: REFINES 父保 ACTIVE / SUPERSEDES 父转 ARCHIVED。"""
    if edge_type == EvolutionType.SUPERSEDES and parent.state == DecisionState.ACTIVE:
        raise W2Violation(...)
    # ...

def assert_w14(user_id: UserID, date: date, current_count: int) -> None:
    """W14: 单用户 5/日卡片上限（DB CHECK 双保险）。"""
    if current_count >= DEFAULT_DAILY_CARD_QUOTA:
        raise W14Violation(...)

def assert_w15(user_id: UserID, now: datetime, work_hour_start: int, work_hour_end: int) -> None:
    """W15: 非工作时段暂停非紧急卡片。"""
    local_hour = now.astimezone(...).hour
    if not (work_hour_start <= local_hour < work_hour_end):
        raise W15Violation(...)
```

### 3.2 `cache.py`（最简 ~80 行）

```python
from cachetools import TTLCache

_CACHE: TTLCache = TTLCache(maxsize=10000, ttl=HOT_PATH_CACHE_TTL_SECONDS)  # 300s

def cache_get(key: str) -> Any | None: ...
def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None: ...
def cache_invalidate(pattern: str) -> int: ...   # glob 模式
```

### 3.3 `llm_gateway.py`（mock-first ~180 行）

- 模块级 TPM 计数器（按 LLMCategory 维度）
- `light_llm_extract` / `heavy_llm_extract` 双入口
- mock 路径：`USE_LLM_MOCK=1` → 返回 `{"evolution_type": "ROOT", "confidence": 0.95, "reasoning": "mock"}` 字符串
- 真路径：`httpx.post` 到 `DOUBAO_BASE_URL` + EP；超时 5s/15s
- W12：日预算耗尽 → `LLMQuotaExceededError`；mock 模式不触发
- 调用前 `compute_embedding` / `light_llm_extract` 等 wrapper 函数都先查 mock env，再决定路径

### 3.4 `embeddings.py`（mock-first ~70 行）

```python
def compute_embedding(text: str) -> list[float]:
    if settings.use_llm_mock:
        # deterministic：hash → 1024 浮点向量，归一化
        h = hashlib.sha256(text.encode()).digest()
        # 拓展到 1024 维（4 字节/dim → 8 倍重复）
        ...
        return _normalize(vector)
    else:
        return _real_doubao_embedding(text)
```

### 3.5 `feishu_client.py`（mock-first ~100 行）

```python
def feishu_call(
    endpoint: str,
    method: Literal["GET", "POST", "PUT", "DELETE"],
    payload: dict | None = None,
    *,
    direction: Literal["OUT", "IN", "HOOK"] = "OUT",
) -> FeishuResponse:
    # 1) W13 强制：先 INSERT trace_log
    trace_id = _generate_trace_id()
    _insert_trace_log(trace_id, endpoint, direction, payload)
    
    # 2) mock or 真调
    if settings.use_feishu_mock:
        return FeishuResponse(code=0, msg="ok", data={}, trace_id=trace_id, latency_ms=10)
    else:
        return _real_feishu_call(...)
```

---

## 4. DoD

- [ ] 5 utils 文件创建 + 1 单测，~510 行（±20%）
- [ ] `mypy --strict memory_engine/utils/` Success
- [ ] `pre-commit run --all-files` 全过（含 validate-consistency）
- [ ] `pytest -q tests/unit/` ≥ 81 passed（73 + 至少 8 新增）
- [ ] `pytest -m integration` 仍 5 passed（无退化）
- [ ] `USE_LLM_MOCK=1` 模式下 mock 返回 deterministic
- [ ] 一次冒烟：完整 Hot Path 流程模拟（cache_set / cache_get / W14 assert）
- [ ] T-005 ticket 状态行 ✅
- [ ] PROGRESS Day 16 条目

---

## 5. 风险

| 风险 | 应对 |
|:---|:---|
| time-constrained 6-8h 内可能写不完 5 模块 | 严格按 P0 → P1 → P2 顺序；P0 必须完成（invariants + cache + 测试），P2 feishu_client 可缩水 |
| Doubao API 真调仍可能 mypy 卡 httpx 类型 | mock 模式作主路径；真路径标 `# type: ignore[no-any-unimported]` 局部豁免 |
| `cachetools` 类型不友好 | pyproject `[[tool.mypy.overrides]]` 已 ignore_missing_imports；用 cast 收窄返回 |
| `apscheduler` 任务未起 → batch_decay 无人调 | 不在本 ticket 范围；T-006 时再装调度器或用 cron 替代 |

---

## 6. 验证步骤（在 WSL 里）

```bash
cd ~/FeishuAI-STZ && git pull origin main
uv sync --extra dev

# 1) 5 utils import 冒烟
uv run python -c "
from memory_engine.utils import light_llm_extract, heavy_llm_extract
from memory_engine.utils import cache, embeddings, feishu_client, invariants
print('5 utils OK')
"

# 2) mock 模式 deterministic 验证
USE_LLM_MOCK=1 uv run python -c "
from memory_engine.utils.embeddings import compute_embedding
v1 = compute_embedding('hello')
v2 = compute_embedding('hello')
assert v1 == v2, 'deterministic mock 应可重复'
print('mock embedding OK len:', len(v1))
"

# 3) 单测全过
uv run pytest -q tests/unit/

# 4) pre-commit 全过
uv run pre-commit run --all-files

# 5) 集成测无退化
uv run pytest -m integration
```

---

> **状态**：📝 草稿（2026-05-13 创建，time-constrained 模式 6-8h 实施）
> **后续 ticket**：T-006 M1 切片（端到端 webhook → cold_path → DB 落库）；以及 v1.1 真接入路径（Doubao + 飞书）
