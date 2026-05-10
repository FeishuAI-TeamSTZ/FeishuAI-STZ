# 04 · 主线工程实施纲要 (ENGUIDE)

> **文档编号**：04-ENGUIDE
> **版本**：v1.0.1
> **生效日期**：2026-04-27（v1.0.1 修订日：2026-05-04）
> **上级文档**：[01-CONSTITUTION.md](./01-CONSTITUTION.md) v1.3
> **架构对齐**：[02-DESIGN.md](./02-DESIGN.md) v3.3-focused
> **数据契约**：[03-SCHEMA.md](./03-SCHEMA.md) v1.0.1

---

## 0. 文档定位

### 0.1 本文是什么

- 描述**仓库目录结构、编码约定、模块接口契约、测试纪律、CI / PR 流程**
- §8 接口契约总表 = **任何代码 ticket 启动的前置条件**（CLAUDE.md §2.1）
- 不在本文 §8 中存在的接口 → 不允许在 PR 中出现

### 0.2 本文不是什么

- 不是算法说明（归 02-DESIGN）
- 不是数据契约（归 03-SCHEMA）
- 不是评测协议（归 06-benchmark-design）
- 不是跨源接入边界（归 05-edge-discipline）
- 不是 ticket 模板（ticket 在 `tickets/` 目录单独维护）

### 0.3 修改流程

| 改动级别 | 流程 |
|:---|:---|
| 编码风格 / 配置常量微调 | 字段级，PR 即可 |
| 新增 / 修改 §8 接口签名 | 条款级：**必须先改本文 → 再改实现**；任何 PR 中出现"接口先于本文存在"即视为违约 |
| 改变 §1 目录布局 / §3 数据三层 | 范围级：active 贡献者 ✅ |

---

## 1. 仓库目录布局

```
FeishuAI-STZ/
├── CLAUDE.md                     行为约束
├── PROGRESS.md                   工作记录（CLAUDE.md §2.8）
├── README.md
├── .gitignore
├── pyproject.toml                项目配置（Python 3.11+ / ruff / mypy / pytest）
├── requirements.txt              依赖锁
├── alembic.ini                   迁移配置
│
├── docs/                         文档体系
│   ├── 01-CONSTITUTION.md
│   ├── 02-DESIGN.md
│   ├── 03-SCHEMA.md
│   ├── 04-ENGUIDE.md             ← 本文
│   ├── 05-edge-discipline.md     待建
│   └── 06-benchmark-design.md    待建
│
├── memory_engine/                ── R1 内核工程师领地 ──────────
│   ├── __init__.py
│   ├── config.py                 全局常量（PROVENANCE_TRUST_WEIGHTS / DAILY_LLM_BUDGET 等）
│   ├── models.py                 SQLAlchemy 2.0 ORM；与 schema.sql 1:1
│   ├── types.py                  pydantic v2 业务对象（DecisionAtom / EvolutionJudgment 等）
│   ├── exceptions.py             自定义异常树（见 §8.11）
│   │
│   ├── extractor.py              M1 决策原子提取
│   ├── evolution_judge.py        M2 演化判定 + OPPOSITE_PAIRS
│   ├── reflect_agent.py          M3 Reflect 自审
│   ├── consensus.py              跨源共识度计算（M1 子模块）
│   ├── hot_path.py               M5 Hot Path 检索
│   ├── cold_path.py              M5 Cold Path 编排器
│   ├── cards.py                  M6 卡片分类 + 闸门
│   ├── decay.py                  M7 五维衰减
│   ├── state_machine.py          状态机 + W2 转换
│   │
│   └── utils/
│       ├── __init__.py           re-export light_llm_extract / heavy_llm_extract
│       ├── llm_gateway.py        强制层：所有 LLM 调用唯一入口
│       ├── feishu_client.py      W13 强制层：所有飞书 API 唯一入口
│       ├── cache.py              Hot Path 内存 LRU + 5min TTL
│       ├── embeddings.py         Doubao Embedding v1 包装
│       └── invariants.py         W 不变量运行时检查
│
├── feishu_integration/           ── R2 接入工程师领地 ─────────
│   ├── __init__.py
│   ├── webhook.py                飞书事件 webhook 接收（FastAPI router）
│   ├── message_handler.py        群消息事件 → cold_path
│   ├── doc_handler.py            文档变更事件 → cold_path
│   ├── okr_sync.py               OKR API（v1 fixture，v2 真接入）
│   ├── approval_sync.py          审批 API（v1 fixture）
│   ├── minutes_sync.py           妙记 API（v1 fixture）
│   ├── calendar_sync.py          日历 API（v1 fixture）
│   ├── bot_sender.py             飞书 Bot 发卡片
│   └── card_responder.py         捕获用户卡片响应
│
├── cli/                          ── R2 接入工程师领地 ─────────
│   ├── __init__.py
│   ├── hook.py                   OpenClaw 钩子入口
│   ├── intercept.py              拦截判定逻辑（调 hot_path）
│   └── override.py               --override-decision 处理
│
├── benchmark/                    ── R3 评测+产品工程师领地 ────
│   ├── __init__.py
│   ├── test_robust_recall.py     测试一：抗干扰召回
│   ├── test_supersede_acc.py     测试二：矛盾覆写
│   ├── test_efficiency.py        测试三：效能对比
│   ├── runner.py                 主跑分入口
│   └── fixtures/                 测试数据（详见 06-benchmark-design）
│
├── tests/                        单元测试 + 集成测试（与 benchmark 区分）
│   ├── unit/                     纯单元，全 mock
│   ├── integration/              集成测试，可连真 PG（mock LLM/Feishu）
│   └── fixtures/                 共享 fixture
│
├── scripts/                      运维脚本
│   ├── invariant_check.py        W2/W4 巡检（每 1 min）
│   ├── validate_consistency.py   schema.sql ↔ models.py 漂移检查
│   └── seed_fixtures.py          灌注演示种子数据
│
└── migrations/                   Alembic
    ├── env.py
    └── versions/
        ├── 0001_initial_schema.py
        └── ...
```

**领地纪律（CLAUDE.md §3.1）**：单人 + Claude 模式下，一次会话 / PR 只动一个领地的目录；跨领地改动必须在 PR 描述中显式列出。

---

## 2. 编码约定

| 维度 | 规范 |
|:---|:---|
| Python 版本 | 3.11+（match-case、TypeAlias 友好） |
| 类型注解 | **强制全量**；`mypy --strict` 必过 |
| 格式化 | `ruff format`（替代 black） |
| Lint | `ruff check`（替代 flake8 + isort） |
| 业务对象 | **pydantic v2**（不允许裸 dict / dataclass，除非性能热点且有注释说明） |
| ORM | **SQLAlchemy 2.0 sync API**（不用 async ORM；Session 由 context manager 管理） |
| Web | **FastAPI sync routes**（v1 全同步；并发由 uvicorn worker 解决） |
| HTTP 客户端 | **httpx 同步**（与 FastAPI 风格一致；async 留 v2） |
| 测试 | `pytest` + `pytest-mock` + `pytest-cov`；不用 unittest |
| 日志 | `structlog` JSON 输出（见 §7） |
| 时区 | 全部 `datetime.UTC` 存储；展示前用 `users.timezone` 翻译 |
| 字符串 | f-string 优先；不用 `%` 或 `.format()` |

**禁止**：
- `print()` 调试残留
- 裸 `except:`（必须 `except SpecificException:`）
- 模块级 mutable 全局状态（除 `config.py` 中的 frozen 常量）
- 循环导入（用 `TYPE_CHECKING` 守卫）

---

## 3. 数据三层

```
   ┌──────────────────────┐
   │   API DTO (pydantic) │ ── feishu_integration / cli 边界用
   └──────────┬───────────┘
              │ to_business / from_business
              ▼
   ┌──────────────────────┐
   │  业务对象 (pydantic)  │ ── memory_engine 内部流通
   └──────────┬───────────┘
              │ to_orm / from_orm
              ▼
   ┌──────────────────────┐
   │   ORM (SQLAlchemy)    │ ── 仅 memory_engine.models 触达
   └──────────────────────┘
```

### 3.1 三类数据对象的命名

| 层 | 文件 | 命名后缀 | 示例 |
|:---|:---|:---|:---|
| ORM | `memory_engine/models.py` | `<Entity>Model` | `DecisionModel` |
| 业务 | `memory_engine/types.py` | `<Entity>` | `Decision` / `DecisionAtom` |
| DTO | `feishu_integration/types.py` 等 | `<Entity>DTO` | `FeishuMessageDTO` |

### 3.2 转换规则

```python
class Decision(BaseModel):
    decision_id: UUID
    subject: str
    # ...

    @classmethod
    def from_orm(cls, model: DecisionModel) -> "Decision":
        return cls.model_validate(model, from_attributes=True)

    def to_orm(self) -> DecisionModel:
        return DecisionModel(**self.model_dump())
```

### 3.3 边界规则

- ORM 模型**不许**跨出 `memory_engine` 包；所有 service 函数返回业务对象
- DTO **不许**进入 `memory_engine` 内部；webhook 边界完成 DTO → 业务对象转换
- 业务对象**不持有**数据库 Session

---

## 4. LLM 网关（CLAUDE.md §2.5 强制层）

### 4.1 唯一入口

```python
from memory_engine.utils import light_llm_extract, heavy_llm_extract
from memory_engine.utils.embeddings import compute_embedding
```

**禁止**：在任何 main code path 中直接调用 `requests.post('https://...')` 或 SDK；违反者 PR 直接拒绝。

### 4.2 接口签名（详见 §8.9）

```python
def light_llm_extract(prompt: str, max_tokens: int = 500, *, category: LLMCategory) -> LLMResponse: ...
def heavy_llm_extract(prompt: str, max_tokens: int = 2000, *, category: LLMCategory) -> LLMResponse: ...
def compute_embedding(text: str) -> Vector: ...  # 返回 list[float] 长度 1024
```

### 4.3 内置行为

- **trace_id 自动生成**并写入 `trace_log`（W13 由 §5 飞书网关与本网关共同保证）
- **额度计数**按 `LLMCategory` 分类（见 §9.2）
- **W12 自动降级**：任一 category 当日额度耗尽 → 切本地 7B 量化模型；次日 0:00 UTC+8 恢复
- **重试**：HTTP 5xx 指数退避 3 次；4xx 直接抛
- **超时**：light = 5s；heavy = 15s；embedding = 3s

### 4.4 LLM 调用预算（宪法 §4.1 镜像）

**约束底层 = TPM 1w 单人 / 3w 小组**（火山引擎 Doubao）。下表的"日 calls 预算"由 TPM 派生，仅作每日规划参考；实际 rate-limit 由网关在 per-minute 维度上强制。

| Category | 模型 | 单次 token | 日 calls 预算 | 优先级 |
|:---|:---|:---:|:---:|:---:|
| `EXTRACT_LIGHT` | Doubao 1.6 | ~500 | 3K | P0 |
| `EVOLVE_HEAVY` | Doubao 2.0 | ~800 | 3K | P0 |
| `REFLECT_BORDER` | Doubao 2.0 | ~1K | 1.5K | P1 |
| `CROSS_ALIGN` | Doubao 2.0 | ~1.2K | 1.5K | P1 |
| `DECAY_OFFLINE` | Doubao 1.6 | ~2K | <0.5K | P2 |
| `EMBEDDING` | Doubao Embedding v1 | ~30 (1024 维) | 独立 EP，不挤占以上 | P0 |
| `BUFFER` | — | — | ~0.5K | — |

P0 类预算耗尽 → 整套系统降级（W12 切本地 7B）；P1/P2 耗尽仅本类降级。

**网关强制行为**：
- per-minute token 计数器：连续 60s 累计 ≥ 9000 tokens 时主动降速（避开 10000 hard limit）
- 单 category 日预算耗尽 → raise `LLMQuotaExceededError`
- 接入小组 3w TPM 通道时，网关需读取 `LLM_TPM_TIER` 环境变量切换上限

### 4.5 测试 mock 规约

```python
# tests/unit/conftest.py
@pytest.fixture
def mock_llm(monkeypatch):
    def fake_light(prompt, max_tokens=500, *, category):
        return LLMResponse(content='{"...": "..."}', tokens_used=100, used_local=False)
    monkeypatch.setattr("memory_engine.utils.llm_gateway.light_llm_extract", fake_light)
    # heavy 同理
```

**单测必须 mock；集成测必须 mock；唯一例外是显式 `@pytest.mark.live` 的端到端基准测试。**

---

## 5. 飞书 API 网关（W13 强制层）

### 5.1 唯一入口

```python
from memory_engine.utils.feishu_client import feishu_call
```

### 5.2 接口签名

```python
def feishu_call(
    endpoint: str,           # e.g. "/open-apis/im/v1/messages"
    method: Literal["GET", "POST", "PUT", "DELETE"],
    payload: dict | None = None,
    *,
    direction: Literal["OUT", "IN", "HOOK"] = "OUT",
) -> FeishuResponse: ...
```

### 5.3 W13 强制行为

```
[1] 应用层调 feishu_call(...)
[2] 网关生成 trace_id (uuid hex)
[3] 网关 INSERT trace_log (trace_id, endpoint, direction, request_payload, called_at=now())
        ↑ 若该 INSERT 失败（DB 不可达），网关 raise FeishuTraceLogError；request 不发出
[4] 网关 HTTP 调用
[5] 网关 UPDATE trace_log SET response_payload, http_status, latency_ms, error_message
[6] 返回 FeishuResponse 给调用者
```

**断言**：任何 `feishu_call` 完成后，`trace_log` 中必有该 trace_id 行；W13 在 DB 层 NOT NULL + 应用层网关共同保证。

### 5.4 重试策略

- HTTP 429（限流）：等待 `Retry-After` 头指定秒数后重试（最多 2 次）
- HTTP 5xx：指数退避 1s / 2s / 4s（最多 3 次）
- HTTP 4xx（除 429）：直接抛 `FeishuAPIError`
- 网络错误：同 5xx 处理

---

## 6. 测试纪律（宪法 §5.2 评测先于功能）

### 6.1 三层测试

| 类别 | 目录 | 性质 | 必须 mock |
|:---|:---|:---|:---|
| 单元测试 | `tests/unit/` | 纯函数 / 单类；全部 I/O mock | LLM、飞书 API、DB（用 SQLite in-memory） |
| 集成测试 | `tests/integration/` | 多模块协作；可连真 PG | LLM、飞书 API；DB 用 testcontainers PG |
| 基准测试 | `benchmark/` | 三大主测试；端到端 | 仅在 `@pytest.mark.live` 时连真服务 |

### 6.2 fixture 组织

```
tests/fixtures/
  decisions/
    sample_decision.json        单条决策原子样例
    conflict_pair.json          A→B 矛盾对（测试二用）
  feishu_messages/
    1000_noise.jsonl            抗干扰测试种子
  llm_responses/
    extract_success.json
    evolve_supersedes.json
  embeddings/
    deterministic_seed.json     固定向量种子
```

**fixture 必须先于实现存在**（CLAUDE.md §2.2）；写代码前先把对应 `tests/test_*.py` 函数（哪怕 `pass`）建好。

### 6.3 mock 规约

- LLM mock：`pytest-mock` + `monkeypatch.setattr`，不用 `unittest.mock`
- 飞书 API mock：用 `respx`（httpx mock 框架）或自建 `FeishuClientMock` 类
- DB mock 优先级：单测 → SQLite in-memory；集成测 → testcontainers PG
- 时间 mock：`freezegun` 控制 `datetime.now()`

### 6.4 命名约定

```
tests/unit/test_<module>.py         e.g. test_evolution_judge.py
tests/integration/test_int_<scenario>.py  e.g. test_int_card_pipeline.py
benchmark/test_<test_id>.py         e.g. test_robust_recall.py
```

### 6.5 覆盖率目标

- `memory_engine/` 单测覆盖 ≥ 80%
- `feishu_integration/` 集成测覆盖 ≥ 60%
- `cli/` 单测覆盖 ≥ 70%
- benchmark 不计覆盖率（端到端不要求行覆盖）

---

## 7. 日志与观测

### 7.1 structlog 必填字段

每条 log 行至少带：
- `trace_id`（飞书 / LLM 调用绑定）
- `decision_id`（涉及决策原子时）
- `user_id`（涉及用户操作时）
- `latency_ms`（性能敏感动作）
- `module`（自动注入：模块名）

### 7.2 日志级别

| 级别 | 何时使用 |
|:---|:---|
| `DEBUG` | 开发期辅助；生产环境过滤 |
| `INFO` | 正常业务事件（决策提取、卡片推送、状态转换） |
| `WARNING` | 降级触发、重试发生、巡检发现轻微违反 |
| `ERROR` | 业务级失败（LLM 调用失败、API 4xx） |
| `CRITICAL` | 不变量违反（W2/W13/W14）、DB 不可达 |

**禁止用 `print` 替代日志**。

---

## 8. 接口契约总表（关键章节）

> 每个接口给出：函数签名 + 入参表 + 出参 + 异常 + 副作用 + 前后置条件 + 测试要求。
> **任何 PR 中接口与本表不一致即拒收**。

### 8.1 M1 提取（`memory_engine/extractor.py`）

#### `extract_from_message`

```python
def extract_from_message(msg: FeishuMessage) -> list[DecisionAtom]: ...
```

| 项 | 说明 |
|:---|:---|
| 入参 | `msg: FeishuMessage(message_id, sender_id, group_id, text, sent_at)` |
| 出参 | `list[DecisionAtom]`；若消息非决策性返回 `[]` |
| 异常 | `LLMQuotaExceededError`（W12 触发）/ `ExtractionTimeoutError`（5s 超时） |
| 副作用 | LLM: ≤1× `light_llm_extract(EXTRACT_LIGHT)`；DB: 无写入；API: 无 |
| 前置 | `msg.text` 非空 |
| 后置 | 返回的每个 DecisionAtom 七字段非空、provenance ∈ enum、confidence ∈ [0, 1] |
| 测试 | 单测 mock LLM；覆盖：纯闲聊返回 []、单决策返回 1 条、多决策返回 N 条、超时抛异常 |

#### `extract_from_doc_change`

```python
def extract_from_doc_change(change: FeishuDocChange) -> list[DecisionAtom]: ...
```

类似 `extract_from_message`；provenance = `DOC_SYNCED`。

#### `batch_extract`

```python
def batch_extract(events: list[Event]) -> list[DecisionAtom]: ...
```

按 event 类型分发到上述函数；不并发（同步串行）。

---

### 8.2 M2 演化判定（`memory_engine/evolution_judge.py`）

#### `find_potential_parents`

```python
def find_potential_parents(candidate: DecisionAtom, *, top_k: int = 3) -> list[Decision]: ...
```

| 项 | 说明 |
|:---|:---|
| 入参 | candidate（七字段完整）；top_k 候选父决策数 |
| 出参 | `list[Decision]`，按相似度降序；若无候选返回 `[]`（candidate 即 ROOT） |
| 异常 | `DBQueryError` |
| 副作用 | DB: SELECT；LLM: 0；走 §8.5 hot_path.precise_match → fallback semantic_search |
| 前置 | `candidate.subject` / `predicate` 非空 |
| 后置 | 返回的 Decision 状态 ∈ {ACTIVE, STALE, HYPOTHESIS}（不返回 GHOST/ARCHIVED） |

#### `judge_evolution`

```python
def judge_evolution(candidate: DecisionAtom, parent: Decision | None) -> EvolutionJudgment: ...
```

| 项 | 说明 |
|:---|:---|
| 入参 | candidate；parent（None 表示 ROOT 判定） |
| 出参 | `EvolutionJudgment(evolution_type, confidence, reasoning, used_llm)` |
| 异常 | `LLMQuotaExceededError` / `LLMResponseInvalidError`（JSON 解析失败） |
| 副作用 | LLM: ≤1× `heavy_llm_extract(EVOLVE_HEAVY)`；OPPOSITE_PAIRS 命中时跳过 LLM |
| 前置 | parent 若非 None，其 state ∈ {ACTIVE, STALE, HYPOTHESIS} |
| 后置 | parent IS None → type = ROOT；parent NOT None → type ∈ {SUPERSEDES, REFINES, GENERALIZES, BRANCHES}；reasoning ≤ 200 字 |
| 测试 | 单测覆盖：四种 type 解析、OPPOSITE_PAIRS 命中跳过 LLM、无效 JSON 抛异常 |

#### `commit_evolution`

```python
def commit_evolution(child: DecisionAtom, parent: Decision | None, judgment: EvolutionJudgment) -> Decision: ...
```

| 项 | 说明 |
|:---|:---|
| 副作用 | DB: INSERT decisions（child）；若 type=SUPERSEDES → UPDATE parent.state='ARCHIVED' (W2)；INSERT decision_embeddings |
| 后置 | 返回新 Decision；触发 §8.12 事件 `decision.committed`、可能触发 `decision.archived`（父） |

---

### 8.3 M3 Reflect（`memory_engine/reflect_agent.py`）

#### `should_reflect`

```python
def should_reflect(judgment: EvolutionJudgment) -> bool: ...
```

返回 `True` 当且仅当 `judgment.used_llm AND 0.5 <= judgment.confidence <= 0.85`（02-DESIGN §四 机制三 边界策略）。

#### `reflect`

```python
def reflect(judgment: EvolutionJudgment, ctx: ReflectContext) -> ReflectReport: ...
```

| 项 | 说明 |
|:---|:---|
| 入参 | `ctx: ReflectContext(candidate, parent_pool, history_window=7d)` |
| 出参 | `ReflectReport(quality_score, potential_missed_parent_id, suggested_type, confidence_calibration, reasoning)` |
| 异常 | `LLMQuotaExceededError` |
| 副作用 | LLM: 1× `heavy_llm_extract(REFLECT_BORDER)`；DB: INSERT reflect_logs |
| 后置 | quality_score ∈ [0, 1]；confidence_calibration ∈ [-1, 1]；**绝不 UPDATE decisions 历史值**（W6） |

---

### 8.4 M4 Actor-Aware（`memory_engine/types.py` + `memory_engine/config.py`）

不是模块，是数据规约。

```python
# config.py
PROVENANCE_TRUST_WEIGHTS: Final[dict[Provenance, float]] = {
    Provenance.USER_STATED:       1.00,
    Provenance.OKR_SYNCED:        0.95,
    Provenance.APPROVAL_PASSED:   0.90,
    Provenance.DOC_SYNCED:        0.85,
    Provenance.MEETING_EXTRACTED: 0.70,
    Provenance.SYSTEM_INFERRED:   0.50,
}

CONSENSUS_WEIGHTS: Final[dict[SourceType, float]] = {
    SourceType.OKR:          0.40,  # W9 顶档
    SourceType.DOC:          0.30,
    SourceType.MESSAGE:      0.20,
    SourceType.CALENDAR:     0.05,
    SourceType.APPROVAL:     0.05,
}
```

helpers：
```python
def assign_provenance(source_type: SourceType) -> Provenance: ...
```

---

### 8.5 M5 Hot Path（`memory_engine/hot_path.py`）

#### `precise_match`

```python
def precise_match(subject: str, predicate: str | None = None) -> list[Decision]: ...
```

| 项 | 说明 |
|:---|:---|
| 副作用 | DB: SELECT 走 `idx_decisions_subj_pred_state`；LLM: 0；缓存：先查缓存 |
| 后置 | 仅返回 state ∈ {ACTIVE, STALE, HYPOTHESIS}；按 confidence DESC 排序 |
| 性能 | P95 ≤ 50ms |

#### `semantic_search`

```python
def semantic_search(query_embedding: Vector, *, top_k: int = 5, state_filter: list[State] | None = None) -> list[tuple[Decision, float]]: ...
```

| 项 | 说明 |
|:---|:---|
| 出参 | `list[(Decision, cosine_similarity)]`，按相似度降序 |
| 副作用 | DB: pgvector HNSW 查询；LLM: 0 |
| 性能 | P95 ≤ 150ms（v1 数据量 < 10K） |

#### `get_decision_by_id`

```python
def get_decision_by_id(decision_id: UUID) -> Decision | None: ...
```

走缓存 → DB；命中后访问计数 +1（M7 f_freq 输入）。

#### `query_active_decisions`

```python
def query_active_decisions(subject: str, predicate: str | None = None) -> list[Decision]: ...
```

`precise_match` + state filter = ACTIVE only；CLI 拦截主入口。性能目标 P95 ≤ 200ms（包含访问计数 UPDATE）。

---

### 8.6 M5 Cold Path（`memory_engine/cold_path.py`）

#### `process_event`

```python
def process_event(event: Event) -> ProcessResult: ...
```

```python
class ProcessResult(BaseModel):
    decisions_extracted: list[UUID]
    cards_queued: list[UUID]
    consensus_alerts: list[UUID]
    llm_calls: int
```

| 项 | 说明 |
|:---|:---|
| 副作用 | 完整管线：M1 提取 → M2 找父 + 判定 → M2 提交 → M3 Reflect（可选）→ M6 生成卡片 → M7 触发衰减计算 |
| 异常 | 任一子步骤异常向上抛；事务边界由调用方决定 |
| 性能 | P95 ≤ 3s（02-DESIGN §四 机制五） |

---

### 8.7 M6 卡片（`memory_engine/cards.py`）

#### `classify_conflict`

```python
def classify_conflict(decision_a: Decision, decision_b: Decision) -> ConflictLevel: ...
```

返回 `HARD` / `SOFT` / `NONE`。

#### `decide_card_action`

```python
def decide_card_action(conflict: ConflictLevel, uncertainty: float) -> CardAction: ...
```

```python
class CardAction(BaseModel):
    should_push: bool
    card_type: CardType  # HARD_ASSERTION / SOFT_INQUIRY / GHOST_LOG / ...
```

逻辑（02-DESIGN §四 机制六）：
- HARD → push HARD_ASSERTION
- SOFT + uncertainty > 0.7 → push SOFT_INQUIRY
- SOFT + uncertainty ≤ 0.7 → push GHOST_LOG (silent)
- NONE → no push

#### `enqueue_card`

```python
def enqueue_card(card: Card) -> UUID: ...  # 返回 card_id
```

副作用：DB INSERT cards (status='QUEUED')。

#### `gate_check`

```python
def gate_check(user_id: UserID, card: Card) -> GateResult: ...
```

```python
class GateResult(BaseModel):
    can_push: bool
    blocked_by: Literal["BUDGET", "WORK_HOURS", "DEDUP_24H", None]
```

闸门顺序（02-DESIGN §四 机制六）：
1. **W11 dedup**：查 `idx_cards_dedup`；24h 内同一 (decision_id, related_decision_id) 已推 → BLOCK
2. **W14 budget**：查 `card_quota`；当日 count ≥ max_daily → BLOCK（HARD 拦截除外）
3. **W15 work hours**：查 `users.work_hour_*`；非工作时段 → BLOCK（HARD 拦截除外）

#### `push_due_cards`

```python
def push_due_cards(user_id: UserID, *, limit: int = 5) -> list[UUID]: ...
```

| 项 | 说明 |
|:---|:---|
| 副作用 | DB: SELECT QUEUED cards → ORDER BY priority_score DESC LIMIT limit；逐个 gate_check；通过的调 §8.9 飞书网关推送；UPDATE status='PUSHED', pushed_at；UPDATE card_quota.count++ |
| 后置 | 已推送数 ≤ limit；W14 在 DB CHECK + 应用层 gate_check 双保险 |

#### `record_response`

```python
def record_response(card_id: UUID, response: CardResponse) -> None: ...
```

副作用：UPDATE cards SET response, status='RESPONDED'；若 response=CONFIRMED → 触发 W8 全量清零（§8.8 `handle_w8_reset`）。

---

### 8.8 M7 衰减（`memory_engine/decay.py`）

#### `compute_factors`

```python
def compute_factors(decision: Decision) -> FiveFactors: ...
```

```python
class FiveFactors(BaseModel):
    f_freq: float            # ∈ [0, 1]
    f_consensus: float
    f_semantic: float
    f_uncertainty: float
    f_user_validation: float
```

#### `recompute_uncertainty`

```python
def recompute_uncertainty(decision_id: UUID, *, reason: str = "periodic_batch") -> float: ...
```

| 项 | 说明 |
|:---|:---|
| 出参 | 新的 uncertainty 值 |
| 副作用 | DB: UPDATE decisions（uncertainty / last_decay_calc_at）；INSERT decay_calculations |
| 公式 | `λ(t) = λ_base × f_freq × f_consensus × f_semantic × f_uncertainty × f_user_validation`；`new_uncertainty = clip(prev + λ × Δt_days, 0, 1)`（与 02-DESIGN §四 机制七 + 03-SCHEMA §5.1 一致） |

#### `batch_decay`

```python
def batch_decay(*, max_rows: int = 1000) -> int: ...
```

| 项 | 说明 |
|:---|:---|
| 副作用 | 扫 `state IN ('ACTIVE','STALE','HYPOTHESIS') AND last_decay_calc_at < now()-1min`；逐行调 `recompute_uncertainty`；返回处理行数 |
| 调用 | Celery beat 每 1 min；可手工触发 |

#### `handle_w8_reset`

```python
def handle_w8_reset(decision_id: UUID) -> None: ...
```

W8 全量清零（03-SCHEMA §5.4 SQL 模板）：UPDATE uncertainty=0, access_count=0, confirm_count++, state='ACTIVE'；INSERT decay_calculations(reason='user_response')。

---

### 8.9 共享工具

#### LLM 网关（`memory_engine/utils/llm_gateway.py`）

```python
class LLMCategory(str, Enum):
    EXTRACT_LIGHT = "extract_light"
    EVOLVE_HEAVY = "evolve_heavy"
    REFLECT_BORDER = "reflect_border"
    CROSS_ALIGN = "cross_align"
    DECAY_OFFLINE = "decay_offline"

class LLMResponse(BaseModel):
    content: str
    tokens_used: int
    used_local: bool       # True = 已降级到本地模型
    trace_id: str
    latency_ms: int

def light_llm_extract(prompt: str, max_tokens: int = 500, *, category: LLMCategory) -> LLMResponse: ...
def heavy_llm_extract(prompt: str, max_tokens: int = 2000, *, category: LLMCategory) -> LLMResponse: ...
```

#### 嵌入（`memory_engine/utils/embeddings.py`）

```python
def compute_embedding(text: str) -> list[float]: ...  # 1024-dim Doubao Embedding v1
def cosine_similarity(a: list[float], b: list[float]) -> float: ...
```

#### 飞书网关（`memory_engine/utils/feishu_client.py`）

签名见 §5.2。

```python
class FeishuResponse(BaseModel):
    code: int
    msg: str
    data: dict
    trace_id: str
    latency_ms: int
```

#### 缓存（`memory_engine/utils/cache.py`）

```python
def cache_get(key: str) -> Any | None: ...
def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None: ...
def cache_invalidate(pattern: str) -> int: ...   # glob pattern；返回失效条数
```

v1 实现：进程内 `cachetools.TTLCache`；v2 切 Redis 由配置 `CACHE_BACKEND` 控制。

#### 不变量运行时检查（`memory_engine/utils/invariants.py`）

```python
def assert_w2(parent: Decision, child: Decision, edge_type: EvolutionType) -> None: ...
def assert_w14(user_id: UserID, date: date) -> None: ...
def assert_w15(user_id: UserID, now: datetime) -> None: ...
```

违反时 raise `InvariantViolation`（详见 §8.11）。巡检脚本与运行时双调用。

---

### 8.10 CLI（`cli/hook.py`）

#### `pre_command_hook`

```python
def pre_command_hook(command: str, args: list[str], env: dict[str, str]) -> InterceptDecision: ...
```

```python
class InterceptDecision(BaseModel):
    action: Literal["ALLOW", "BLOCK", "WARN"]
    reason: str | None
    decision_ids: list[UUID]
    trace_id: str
    rendered_card: str | None    # 终端展示的红字
```

| 项 | 说明 |
|:---|:---|
| 副作用 | 走 §8.5 `query_active_decisions`；命中 `FREEZE_*` 谓词且 confidence > 0.7 → BLOCK |
| W5 | 任何异常 → 返回 ALLOW（默认放行，绝不阻塞 workflow） |
| 性能 | P95 ≤ 200ms（Hot Path 目标） |

#### `post_command_hook`

```python
def post_command_hook(command: str, args: list[str], exit_code: int, decision_ids: list[UUID]) -> None: ...
```

副作用：调 §8.9 飞书网关 → Bot 群消息回写"@user 的命令受决策 X 影响"。

---

### 8.11 异常体系

```
Exception
└── MemoryEngineError                   ── 所有自定义异常的祖先
    ├── LLMError
    │   ├── LLMQuotaExceededError       W12 触发降级
    │   ├── LLMTimeoutError
    │   └── LLMResponseInvalidError     JSON 解析失败
    ├── FeishuError
    │   ├── FeishuAPIError              4xx / 5xx 持久失败
    │   ├── FeishuTraceLogError         W13 trace_log INSERT 失败
    │   └── FeishuRateLimitError        429 但已重试用尽
    ├── DBError
    │   ├── DBQueryError
    │   └── DBConsistencyError          schema.sql ↔ models.py 漂移
    ├── InvariantViolation              W1–W15 任一违反
    │   ├── W2Violation
    │   ├── W13Violation
    │   ├── W14Violation
    │   └── ... (按需扩展)
    ├── ExtractionError
    │   ├── ExtractionTimeoutError
    │   └── InvalidDecisionAtomError    七字段不完整
    └── ConfigError                     配置错误
```

**纪律**：
- 业务代码不允许 `raise Exception(...)`，必须用上述自定义类
- 所有 `MemoryEngineError` 子类必须有 `trace_id` 属性（便于日志关联）
- 不允许把异常吞掉（必须 re-raise 或转换为更高层异常）

---

### 8.12 跨模块依赖与事件

**v1**：模块间直接函数调用（同进程，同步）。

```
webhook (FastAPI)
     │
     ▼
message_handler.py
     │
     ▼  调
cold_path.process_event(event)
     │
     ├──► extractor.extract_from_message    (M1)
     ├──► evolution_judge.find_potential_parents
     ├──► evolution_judge.judge_evolution   (M2)
     ├──► reflect_agent.reflect             (M3, 仅边界 confidence)
     ├──► evolution_judge.commit_evolution  (落库)
     ├──► cards.decide_card_action          (M6)
     ├──► cards.enqueue_card
     └──► decay.recompute_uncertainty       (M7, 异步触发)
```

**v2 演进**（v1 不做）：引入事件总线（Redis Streams 或 Postgres LISTEN/NOTIFY）；事件清单：

| 事件 | 发布方 | 订阅方 |
|:---|:---|:---|
| `decision.extracted` | extractor | evolution_judge / consensus |
| `decision.committed` | evolution_judge | cache / decay / cards |
| `decision.archived` | state_machine | cache（失效）/ cards（撤回相关卡片） |
| `decision.confirmed` | cards | decay（W8 触发） |
| `card.pushed` | cards | (notification / metrics) |
| `llm.quota_exceeded` | llm_gateway | cold_path（降级路由） |

---

## 9. 配置与环境

### 9.1 必需环境变量

| 变量 | 必填 | 说明 | 示例 / 默认 |
|:---|:---:|:---|:---|
| `DATABASE_URL` | ✓ | PG 连接串 | `postgresql+psycopg://memory:memory@localhost:5432/memory` |
| `DOUBAO_API_KEY` | ✓ | Doubao Heavy / Light / Embedding 共用 API Key | (火山引擎认领) |
| `DOUBAO_HEAVY_ENDPOINT_ID` | — | Doubao 2.0 EP（M2 演化判定 / M3 Reflect / 跨源对齐） | `ep-202604-xxxxxxxx` |
| `DOUBAO_LIGHT_ENDPOINT_ID` | — | Doubao 1.6 EP（M1 提取 / 离线参数校准） | `ep-202604-xxxxxxxx` |
| `DOUBAO_EMBEDDING_ENDPOINT_ID` | — | Doubao Embedding v1 EP（1024 维向量） | `ep-202604-xxxxxxxx` |
| `DOUBAO_BASE_URL` | — | 火山方舟 Inference API 根 | `https://ark.cn-beijing.volces.com/api/v3` |
| `LLM_TPM_TIER` | — | TPM 档位（`single` = 1w / `group` = 3w）；网关 §4.4 据此调上限 | `single` |
| `FEISHU_APP_ID` | ✓ | 飞书应用 ID | — |
| `FEISHU_APP_SECRET` | ✓ | 飞书应用密钥 | — |
| `FEISHU_VERIFICATION_TOKEN` | ✓ | webhook 验证 token | — |
| `FEISHU_ENCRYPT_KEY` | — | 飞书事件加密 key（开启加密时填） | — |
| `LOG_LEVEL` | — | 日志级别 | `INFO` / `DEBUG` |
| `ENVIRONMENT` | — | 运行环境 | `development` / `staging` / `production` |
| `CACHE_BACKEND` | — | `memory` (v1) / `redis` (v2) | `memory` |
| `REDIS_URL` | — | 仅当 `CACHE_BACKEND=redis` 时填 | — |

### 9.2 `config.py` 必需常量

```python
# memory_engine/config.py
from typing import Final

DAILY_LLM_BUDGET: Final[dict[LLMCategory, int]] = {
    LLMCategory.EXTRACT_LIGHT:  3000,
    LLMCategory.EVOLVE_HEAVY:   3000,
    LLMCategory.REFLECT_BORDER: 1500,
    LLMCategory.CROSS_ALIGN:    1500,
    LLMCategory.DECAY_OFFLINE:   500,
}

PROVENANCE_TRUST_WEIGHTS: Final[dict[Provenance, float]] = {...}  # §8.4
CONSENSUS_WEIGHTS: Final[dict[SourceType, float]] = {...}          # §8.4

# 阈值
UNCERTAINTY_CARD_THRESHOLD: Final[float] = 0.7      # 02-DESIGN §四 机制六
REFLECT_CONFIDENCE_LOW: Final[float] = 0.5
REFLECT_CONFIDENCE_HIGH: Final[float] = 0.85
ACTIVE_CONFIDENCE_MIN: Final[float] = 0.85          # state=ACTIVE 入口阈值

# 闸门
DEFAULT_DAILY_CARD_QUOTA: Final[int] = 5            # W14
WORK_HOUR_START_DEFAULT: Final[int] = 9             # W15
WORK_HOUR_END_DEFAULT: Final[int] = 19

# 衰减
DECAY_LAMBDA_BASE: Final[float] = 0.05              # 待 06-benchmark 校准
DECAY_BATCH_INTERVAL_SECONDS: Final[int] = 60       # Celery beat 周期

# 缓存
HOT_PATH_CACHE_TTL_SECONDS: Final[int] = 300        # 5 min (W7)
```

### 9.3 配置加载

```python
# memory_engine/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    doubao_api_key: str
    # ...
    class Config:
        env_file = ".env"

settings = Settings()  # 单例
```

---

## 10. CI / Pre-commit

### 10.1 pre-commit hooks（`.pre-commit-config.yaml`）

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff-format
      - id: ruff
        args: ["--fix"]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
        args: ["--strict"]
  - repo: local
    hooks:
      - id: validate-consistency
        name: schema.sql ↔ models.py 漂移检查
        entry: python scripts/validate_consistency.py
        language: python
        pass_filenames: false
```

### 10.2 GitHub Actions

| Job | 触发 | 步骤 |
|:---|:---|:---|
| `lint` | PR + push | ruff format check + ruff check + mypy --strict |
| `test-unit` | PR + push | pytest tests/unit/ --cov=memory_engine |
| `test-integration` | PR + push | testcontainers PG + pytest tests/integration/ |
| `validate-consistency` | PR + push | scripts/validate_consistency.py |
| `benchmark` | 仅 Day 12+ 手动 trigger | benchmark/runner.py（耗 LLM 额度） |

---

## 11. PR 模板（`.github/pull_request_template.md`）

```markdown
## 改动范围

- ticket: <编号 / 链接>
- 04-ENGUIDE §8 接口编号: <如 §8.2 judge_evolution>
- 触及领地: <R1 / R2 / R3>

## 改动文件

- `memory_engine/...`
- `tests/unit/...`
- ...

## DoD 自检（CLAUDE.md §3.2）

- [ ] 实现了 ticket 描述的功能（且仅实现该功能）
- [ ] 单测通过（含 fixture）
- [ ] docstring 与实际行为一致
- [ ] 接口签名与 04-ENGUIDE §8 完全一致
- [ ] 至少 1 名 active 贡献者 review
- [ ] PROGRESS.md 已追加（CLAUDE.md §2.8）

## LLM 调用次数（开发 + 测试）

- 开发期总计: N 次（其中 light: a / heavy: b / embedding: c）
- 测试期：全 mock，0 次

## 范围合规

- [ ] 不在宪法 §3.2 Out of Scope 列表中
- [ ] 不引入 requirements.txt 之外的新依赖
- [ ] 跨领地改动已显式列出（如适用）

## 建议（Out of scope，不在本 PR 实现）

- ...
```

PR 标题约定：`<type>(<scope>): <一句话>`，type ∈ {feat, fix, refactor, docs, test, chore, ci}。

---

## 附录 A：异常类完整清单

详见 §8.11 异常体系图；实现位置 `memory_engine/exceptions.py`。

每个异常类必须：
- 继承 `MemoryEngineError`
- 构造函数接收 `trace_id: str` 与可选 `extra: dict`
- 定义 `__str__` 输出含 trace_id 的可读消息
- 在 `exceptions.py` 中按类别分组

---

## 附录 B：模块依赖图

```
            ┌─────────────────────────────────┐
            │  feishu_integration / cli       │  R2
            └──────────────┬──────────────────┘
                           │ 调用
            ┌──────────────▼──────────────────┐
            │     cold_path / hot_path         │
            │     (memory_engine 编排层)       │  R1
            └──────────────┬──────────────────┘
                           │
   ┌──────────┬────────────┼────────────┬──────────┐
   ▼          ▼            ▼            ▼          ▼
extractor  evolution_  reflect_     cards    decay   ← M1–M7 业务模块
           judge       agent
   │          │            │            │          │
   └──────────┴────────────┼────────────┴──────────┘
                           ▼
            ┌──────────────────────────────────┐
            │  utils/                           │
            │  - llm_gateway   (CLAUDE.md §2.5) │
            │  - feishu_client (W13)            │
            │  - cache / embeddings / invariants│
            └──────────────┬──────────────────┘
                           │
            ┌──────────────▼──────────────────┐
            │  models.py  (SQLAlchemy ORM)    │
            │  config.py  (Final 常量)        │
            │  types.py   (pydantic 业务对象) │
            └──────────────┬──────────────────┘
                           │
            ┌──────────────▼──────────────────┐
            │       PostgreSQL 16             │
            │       (含 pgvector)              │
            └──────────────────────────────────┘

benchmark/  ←──仅依赖 cold_path / hot_path 顶层 API；不触达内部模块  R3
tests/      ←──同上 + utils mock
```

**循环依赖红线**：M1–M7 之间不允许直接相互调用；必须经由 `cold_path` 编排或显式接口（如 `decay.recompute_uncertainty` 被 `cards` 调）。`utils/` 不允许调任何 M1–M7 业务模块。

---

## 附录 C：版本历史

| 版本 | 日期 | 变更 |
|:---|:---|:---|
| v1.0 | 2026-04-27 | 初稿。锁定 Python 3.11+ / SQLAlchemy 2.0 sync / pydantic v2 / FastAPI sync routes；§8 接口契约总表覆盖 M1–M7 + 共享工具 + CLI（共 ~25 函数签名）；W13/W14 双层强制（DB + 网关 + 巡检） |
| v1.0.1 | 2026-05-04 | §9.1 环境变量表与 `.env.example` 对齐：拆分 Doubao 三档 EP（`HEAVY` / `LIGHT` / `EMBEDDING`）+ `DOUBAO_BASE_URL`；新增 `LLM_TPM_TIER`（§4.4 网关消费）+ `ENVIRONMENT` + `REDIS_URL` + `FEISHU_ENCRYPT_KEY`；标注必填 / 选填两栏 |
