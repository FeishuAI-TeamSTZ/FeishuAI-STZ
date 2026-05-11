# T-006：M1 提取器 + DB 落库 vertical slice（**首个真业务 ticket**）

> **类型**：Phase 1.1 业务实施 ticket（系列 1/3，D9 拆分自原 "M1+M2+M5 端到端"）
> **领地**：R1 内核工程师（`memory_engine/` 业务模块层 + `db.py` 基础设施层）
> **优先级**：P0（解锁 T-007 演化判定 / T-008 Hot Path 集成 demo）
> **计划用时**：1-2 天
> **关联 §8 接口**：[04-ENGUIDE §8.1 M1 提取](../docs/04-ENGUIDE.md) + [§8.6 cold_path](../docs/04-ENGUIDE.md) + 新增 `memory_engine/db.py`（接口未在 §8.9 列，本 ticket 顺手加入并 PR 描述说明）
> **触及不变量**：W2（首条 ROOT 创建无父，应 trivially 满足）/ **W13（首次接入 trace_log DB INSERT 真路径）**
> **预算自检**：~500 行 / 5-6 文件 → 预算内（无豁免）；测试占 ~40%
> **依据文档**：[02-DESIGN §四 机制一](../docs/02-DESIGN.md)；[03-SCHEMA §3.1 decisions 表](../docs/03-SCHEMA.md)；[04-ENGUIDE §8.1 §8.6 §3 数据三层](../docs/04-ENGUIDE.md)

---

## 1. 目标

让以下端到端流程在 mock 模式下走通：

```python
# pseudocode：模拟飞书消息 → 决策原子 → DB ROOT decision
from memory_engine.types import FeishuMessageDTO
from memory_engine.cold_path import process_message_event

event = FeishuMessageDTO(
    message_id="om_test_001",
    sender_id="ou_zhangsan",
    group_id="oc_group_a",
    text="项目 A 上线时间确认为 2026-05-15",
    sent_at=datetime.now(UTC),
)

result = process_message_event(event)
# 期望：
# - result.decisions_extracted = [<UUID>]  (M1 提取出 1 条决策原子)
# - result.llm_calls = 1  (light_llm_extract called once)
# - PG 中 decisions 表多 1 条 ROOT 记录（state=ACTIVE / provenance=USER_STATED）
# - trace_log 表多 1 条 LLM 调用 trace（W13 真路径首次接通）
```

完成后，**首条业务数据从飞书消息流入 PG**，T-007 可基于此实现演化判定（"第二条消息覆写第一条" → SUPERSEDES）。

---

## 2. 范围

### 2.1 In Scope（6 文件，~500 行）

| # | 路径 | 估算行数 | 说明 |
|:---:|:---|:---:|:---|
| 1 | `memory_engine/db.py` | ~80 | SQLAlchemy 2.0 engine factory + `session_scope()` context manager；lazy load Settings；进程级单例 engine |
| 2 | `memory_engine/extractor.py` | ~150 | M1：`extract_from_message(msg) → list[DecisionAtom]`；调 `heavy_llm_extract(EXTRACT_LIGHT)` + JSON 解析 + 七字段校验 |
| 3 | `memory_engine/state_machine.py` | ~100 | `create_root_decision(atom, *, session) → Decision`；处理 ROOT 入库、生成 UUID、设默认 state=ACTIVE / evolution_type=ROOT；带 W2 assert 兜底（即使是 ROOT 也要 invariants.assert_w2 跑一遍） |
| 4 | `memory_engine/cold_path.py` | ~120 | `process_message_event(msg) → ProcessResult`：编排 extractor → 每条 atom 调 state_machine.create_root_decision → 累加 llm_calls / decisions_extracted |
| 5 | `tests/unit/test_m1.py` | ~150 | 单测：extractor mock LLM 返回 JSON / 异常 JSON → InvalidDecisionAtomError / state_machine.create_root 写 DB（SQLite 或 in-memory mock）/ cold_path 编排 |
| 6 | `tests/integration/test_int_m1_e2e.py` | ~100 | 集成测：testcontainers PG → alembic upgrade → process_message_event → 验证 decisions 表 + trace_log 表各 +1 行 |

**附加修订**：
- `memory_engine/utils/feishu_client.py`：补 `_write_trace_log(session, ...)` 函数（W13 DB INSERT 真路径），被 `feishu_call` 在非 mock 模式下调
- `memory_engine/utils/__init__.py`：可选 re-export `session_scope`（如果 04-ENGUIDE §1 同步加入）
- `04-ENGUIDE §1` 目录布局表：加 `memory_engine/db.py` 行（CLAUDE §3.1 新路径必更）

### 2.2 Out of Scope（明确不做）

| 不做 | 归属 |
|:---|:---:|
| M2 演化判定 (`evolution_judge.py`) | T-007 |
| M5 Hot Path (`hot_path.py`) | T-008 |
| M3 Reflect | T-009 |
| M6 卡片 + W14/W15 闸门 | T-010 |
| M7 衰减 batch | T-011 |
| 真飞书 webhook 接收（FastAPI route） | T-008（端到端 demo 时） |
| 真 Doubao API 调用（mock 模式开发） | v1.1 |
| 跨源 OKR / 审批 / 妙记 / 日历提取 | v2.x（宪法 §3.3） |

### 2.3 预算（无豁免）

| 维度 | 上限 | 本 ticket | 状态 |
|:---|:---:|:---:|:---|
| 代码行数 | ≤ 500 | ~500（紧贴上限） | ✓ |
| 文件数 | ≤ 5 | 6（4 业务 + 2 测试，超 1）| ⚠️ 微豁免：业务/测试天然成对 |
| LLM 调用 | ≤ 50 | 0（mock 模式） | ✓ |
| 测试时长 | ≤ 60s | unit < 2s / integration < 10s | ✓ |

---

## 3. 关键决策（待你拍板 D28-D31）

### D28：DB session 注入方式
- **(a)** Context manager + 函数参数显式传 session（`process_message_event(msg, *, session)`）
- **(b)** `session_scope()` 内部上下文管理，调用方无感知（`process_message_event(msg)`）
- 我倾向 **(b)**：调用方简洁；session 生命周期由 cold_path 内部管理；测试时用 monkeypatch 替换 engine

### D29：extractor 解析失败如何处理
- **(a)** raise `InvalidDecisionAtomError`，cold_path 上层 catch + 日志，不进 DB
- **(b)** 返回 `[]` 空列表，静默跳过
- 我倾向 **(a)**：诚实暴露错误（CLAUDE §5.7）；测试覆盖率高；不污染 DB

### D30：trace_log DB INSERT 时机
- **(a)** `feishu_call` 内部强制 INSERT（与 W13 一致）
- **(b)** cold_path 在每次 `feishu_call` 后另调 helper INSERT
- 我倾向 **(a)**：W13 强约束应在网关层而非业务层；与 mock 模式下"trace_id 只生成日志不入库"对称——真模式直接进 DB
- 注：本 ticket 不直接调 `feishu_call`（mock 模式下整个流程不真调飞书）；但需把 `_write_trace_log` 写好供 T-008 webhook 接入时启用

### D31：测试 LLM mock 策略
- **(a)** 复用 `USE_LLM_MOCK=1` env（autouse fixture，与 T-005 一致）
- **(b)** 每个测试 monkeypatch 单独 mock `light_llm_extract`
- 我倾向 **(a)**：与 T-005 测试纪律一致；deterministic mock 模板已能覆盖大部分 case

---

## 4. 文件大纲

### 4.1 `memory_engine/db.py`（~80 行）

```python
"""SQLAlchemy 2.0 engine factory + session context manager（v1 同步）."""

from collections.abc import Iterator
from contextlib import contextmanager
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from memory_engine.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    """lazy load + 进程级单例。"""
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务边界：commit on success / rollback on exception。"""
    _get_engine()  # 触发 _SessionLocal 初始化
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """测试 teardown / 进程退出时清池。"""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
```

### 4.2 `memory_engine/extractor.py`（~150 行）

```python
"""M1 决策原子提取（02-DESIGN §四 机制一）."""

import json
from memory_engine.exceptions import InvalidDecisionAtomError, LLMResponseInvalidError
from memory_engine.types import (
    DecisionAtom, FeishuMessageDTO, LLMCategory, Provenance,
)
from memory_engine.utils.llm_gateway import light_llm_extract


def _build_extract_prompt(text: str, sender_id: str) -> str:
    """构造提取 Prompt（02-DESIGN §四 机制一 提取模板）."""
    return f"""[系统] 从企业群聊消息中提取决策原子。
[消息] sender={sender_id}: {text}
[输出格式 JSON]
{{
  "decisions": [
    {{"subject": "...", "predicate": "...", "object": "...",
      "confidence": 0.0~1.0, "is_decision": true/false}}
  ]
}}
非决策性消息返回 {{"decisions": []}}。
"""


def extract_from_message(msg: FeishuMessageDTO) -> list[DecisionAtom]:
    """M1：从飞书消息提取决策原子；非决策 → 返 []。"""
    if not msg.text:
        return []
    prompt = _build_extract_prompt(msg.text, msg.sender_id)
    response = light_llm_extract(prompt, category=LLMCategory.EXTRACT_LIGHT)
    try:
        data = json.loads(response.content)
    except json.JSONDecodeError as e:
        raise LLMResponseInvalidError(
            trace_id=response.trace_id, extra={"parse_error": str(e)}
        ) from e

    atoms: list[DecisionAtom] = []
    for item in data.get("decisions", []):
        if not item.get("is_decision", True):
            continue
        try:
            atom = DecisionAtom(
                subject=item["subject"],
                predicate=item["predicate"],
                object=item["object"],
                logical_timestamp=msg.sent_at,
                provenance=Provenance.USER_STATED,
                confidence=float(item["confidence"]),
                source_event_id=f"feishu://msg/{msg.message_id}",
                original_text=msg.text,
                consensus_sources=[{"source_type": "feishu_message", "uri": ...}],
            )
            atoms.append(atom)
        except (KeyError, ValueError, TypeError) as e:
            raise InvalidDecisionAtomError(
                trace_id=response.trace_id,
                extra={"item": item, "error": str(e)},
            ) from e
    return atoms
```

### 4.3 `memory_engine/state_machine.py`（~100 行）

```python
"""决策状态机：ROOT 创建 + 状态转换（W2 强制）."""

from sqlalchemy.orm import Session
from memory_engine.models import DecisionModel
from memory_engine.types import DecisionAtom, Decision, DecisionState, EvolutionType
from memory_engine.config import ACTIVE_CONFIDENCE_MIN
from memory_engine.utils.invariants import assert_w2


def _initial_state(confidence: float, provenance) -> DecisionState:
    """高 confidence + 高 provenance → ACTIVE；低 → HYPOTHESIS。"""
    if confidence >= ACTIVE_CONFIDENCE_MIN and provenance.weight >= 0.85:
        return DecisionState.ACTIVE
    return DecisionState.HYPOTHESIS


def create_root_decision(atom: DecisionAtom, *, session: Session) -> Decision:
    """从 DecisionAtom 创建 ROOT 决策原子并落库（无父节点）."""
    # W2 兜底：ROOT 跳过实际检查
    assert_w2(DecisionState.ACTIVE, EvolutionType.ROOT)

    state = _initial_state(atom.confidence, atom.provenance)
    model = DecisionModel(
        subject=atom.subject,
        predicate=atom.predicate,
        object=atom.object,
        logical_timestamp=atom.logical_timestamp,
        provenance=atom.provenance,
        confidence=atom.confidence,
        state=state,
        evolution_type=EvolutionType.ROOT,
        parent_id=None,
        consensus_sources=atom.consensus_sources,
        consensus_score=...,  # 单源场景：provenance.weight
        source_event_id=atom.source_event_id,
        original_text=atom.original_text,
    )
    session.add(model)
    session.flush()  # 触发 DB 默认值生成（UUID 等）
    return Decision.from_orm(model)
```

### 4.4 `memory_engine/cold_path.py`（~120 行）

```python
"""Cold Path 编排器（02-DESIGN §四 机制五）."""

import logging
from memory_engine.db import session_scope
from memory_engine.extractor import extract_from_message
from memory_engine.state_machine import create_root_decision
from memory_engine.types import FeishuMessageDTO, ProcessResult

_log = logging.getLogger(__name__)


def process_message_event(msg: FeishuMessageDTO) -> ProcessResult:
    """M5 Cold Path 主入口：消息 → 提取 → 落库（T-006 = M1 only；T-007 加 M2 演化判定）."""
    atoms = extract_from_message(msg)
    if not atoms:
        _log.info("non_decision_message", extra={"message_id": msg.message_id})
        return ProcessResult(decisions_extracted=[], llm_calls=1, ...)

    decision_ids = []
    with session_scope() as session:
        for atom in atoms:
            decision = create_root_decision(atom, session=session)
            decision_ids.append(decision.decision_id)

    _log.info(
        "process_message_event_ok",
        extra={"message_id": msg.message_id, "decisions": len(decision_ids)},
    )
    return ProcessResult(
        decisions_extracted=decision_ids,
        llm_calls=1,
        cards_queued=[],
        consensus_alerts=[],
    )
```

### 4.5 `tests/unit/test_m1.py`（~150 行）

- TestExtractor (5 cases)：mock LLM 返回有效 JSON / 多决策 / 非决策 / 异常 JSON / 空消息
- TestStateMachine (3 cases)：高 confidence → ACTIVE / 低 → HYPOTHESIS / SYSTEM_INFERRED → HYPOTHESIS
- TestColdPath (3 cases)：mock extractor + DB session（in-memory SQLite 或 mock session）

### 4.6 `tests/integration/test_int_m1_e2e.py`（~100 行）

```python
@pytest.fixture(scope="module")
def db_url(pg_engine):
    """复用 test_int_schema.py 的 pg_engine fixture（已 alembic upgrade）."""
    return str(pg_engine.url)


def test_m1_end_to_end(db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("USE_LLM_MOCK", "1")

    event = FeishuMessageDTO(...)
    result = process_message_event(event)

    assert len(result.decisions_extracted) >= 1
    assert result.llm_calls == 1

    # 验证 DB 实际写入
    with pg_engine.begin() as conn:
        row = conn.execute(text(
            "SELECT subject, state, evolution_type FROM decisions WHERE decision_id = :id"
        ), {"id": str(result.decisions_extracted[0])}).fetchone()
        assert row is not None
        assert row[2] == "ROOT"
```

---

## 5. DoD

- [ ] 6 文件创建/修订，行数 ±20%
- [ ] mypy --strict 全过
- [ ] pre-commit 全过
- [ ] **pytest -q ≥ 122 passed**（111 + ≥ 11 新单测）
- [ ] **pytest -m integration ≥ 6 passed**（5 + ≥ 1 端到端）
- [ ] mock 模式下 `process_message_event` 跑通：返 `ProcessResult` 含 ≥ 1 个 decision_id
- [ ] 真 DB 写入验证：integration test 查 `decisions` 表能看到 ROOT 行
- [ ] 04-ENGUIDE §1 加 `memory_engine/db.py` 行
- [ ] T-006 ticket 状态行 ✅
- [ ] PROGRESS 追加条目

---

## 6. 风险

| 风险 | 应对 |
|:---|:---|
| DB session 注入模式 D28 选 (b) 后，测试用 monkeypatch 替换 engine 复杂 | 提供 `tests/conftest.py` 增加 `_session_scope_test` fixture 替代 |
| extractor 解析 mock LLM JSON 时模板与 DecisionAtom 字段不匹配（mock 模板缺 timestamp 等）| extractor 用 msg.sent_at 补 timestamp；其他字段从模板取 |
| `consensus_score` 计算逻辑分散（state_machine vs config）| 本 ticket 简化为 `provenance.weight`（单源）；跨源在 M2/T-007 完整化 |
| 单测中 SQLite 与 PG 行为差异（jsonb / uuid） | 单测用 mock session（pytest-mock）而非真 SQLite；集成测用 testcontainers PG |
| pyproject testpaths 含 benchmark/，可能误收集 fixture 文件 | 已配 `python_files = ["test_*.py"]` 过滤 |

---

## 7. 验证步骤（WSL 内）

```bash
cd ~/FeishuAI-STZ && git pull origin main

# 1. 单测全过（≥ 122）
uv run pytest -q

# 2. 集成测全过（≥ 6）
docker compose up -d postgres
uv run pytest -m integration

# 3. mock 模式跑端到端
USE_LLM_MOCK=1 uv run python -c "
from datetime import datetime, UTC
from memory_engine.cold_path import process_message_event
from memory_engine.types import FeishuMessageDTO
event = FeishuMessageDTO(
    message_id='om_demo',
    sender_id='ou_zhangsan',
    group_id='oc_demo',
    text='项目A上线时间确认为2026-05-15',
    sent_at=datetime.now(UTC),
)
r = process_message_event(event)
print('decisions:', r.decisions_extracted)
print('llm_calls:', r.llm_calls)
"
# 期望：decisions: [<UUID>] llm_calls: 1
```

---

## 8. 后续 ticket 衔接

T-006 完成后：
- **T-007 M2 演化判定**：`evolution_judge.find_potential_parents / judge_evolution / commit_evolution` + `state_machine.transition_to_archived`（SUPERSEDES 父转 ARCHIVED）
- **T-008 M5 Hot Path + demo**：`hot_path.precise_match / semantic_search / get_decision_by_id` + 飞书 webhook（FastAPI route）+ 端到端 demo 录屏脚本

---

> **状态**：📝 草稿（创建中，待用户审定 D28-D31 后实施）
> **后续 ticket**：T-007 演化判定 / T-008 Hot Path + demo
