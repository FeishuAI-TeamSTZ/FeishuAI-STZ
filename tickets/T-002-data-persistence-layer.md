# T-002：数据持久化层（schema.sql + ORM + 异常）

> **类型**：Phase 0 骨架 ticket（系列 2/5）— 首个**真业务代码** ticket
> **领地**：R1 内核工程师（`memory_engine/`）
> **优先级**：P0（阻塞 T-003 / T-004 / T-005）
> **计划用时**：1 天
> **关联 §8 接口**：04-ENGUIDE §8.11 异常体系；间接支撑 §8.1–§8.10 的所有数据 I/O
> **触及不变量**：W2（演化关系 CHECK）/ W13（trace_log NOT NULL）/ W14（card_quota CHECK ≤ max_daily）—— 全部由 DB 层 CHECK 强制
> **预算豁免**：CLAUDE.md §6 ≤500 行 → 本 ticket ~570 行（超 14%），理由见 §2.3
> **依据文档**：[03-SCHEMA](../docs/03-SCHEMA.md) §1–§9（SQL 落地源）；[04-ENGUIDE](../docs/04-ENGUIDE.md) §3 数据三层 / §8.11 异常体系；[01-CONSTITUTION](../docs/01-CONSTITUTION.md) §5.5 W1–W15 不变量

---

## 1. 目标

让以下命令在 **WSL2 + 已起 PG 容器** 环境下零错误执行：

```bash
# 1) 把 schema.sql 灌进 PG
docker compose exec -T postgres psql -U memory -d memory -f - < schema.sql

# 2) 验证 8 主表 + 1 向量表全部建好
docker compose exec -T postgres psql -U memory -d memory \
  -c "\dt" -c "\dT+" -c "SELECT extname FROM pg_extension WHERE extname='vector';"

# 3) 用 ORM 在 Python 里读写一条决策原子（冒烟测试）
uv run python -c "
from memory_engine.models import DecisionModel, EvolutionType, DecisionState, Provenance
import uuid
d = DecisionModel(
    decision_id=uuid.uuid4(),
    subject='项目A', predicate='RELEASE_DATE', object='2026-05-15',
    logical_timestamp='2026-04-29 10:00+08',
    provenance=Provenance.USER_STATED,
    confidence=0.95,
    evolution_type=EvolutionType.ROOT,
)
print(d)
"

# 4) 异常树冒烟
uv run python -c "
from memory_engine.exceptions import LLMQuotaExceededError, W14Violation
e = LLMQuotaExceededError(trace_id='trc_test', extra={'category': 'EVOLVE_HEAVY'})
print(repr(e))
"

# 5) 既有的 pre-commit + pytest 仍全过
uv run pre-commit run --all-files
uv run pytest -q
```

完成后，**应用层可以拿 ORM 操作 8 主表、抛业务异常**，但还**没有 alembic 迁移、没有 pydantic 业务对象、没有 validate_consistency 脚本**（归 T-003）。

---

## 2. 范围

### 2.1 In Scope（3 个实质文件，~570 行）

| # | 路径 | 估算行数 | 说明 |
|:---:|:---|:---:|:---|
| 1 | `schema.sql` | ~260 | 数据契约 SQL 落地：6 enums + 8 主表 + 1 向量表 + 22 索引 + 全部 CHECK / FK / TRIGGER；与 03-SCHEMA §3 完全镜像 |
| 2 | `memory_engine/models.py` | ~200 | SQLAlchemy 2.0 `Mapped[Type] + DeclarativeBase` 风格；每张表一个 `<Entity>Model` 类；含 `__table_args__` 索引 / CHECK / 关系映射 |
| 3 | `memory_engine/exceptions.py` | ~110 | 04-ENGUIDE §8.11 异常树落地：`MemoryEngineError` 根 + 5 大类（LLM / Feishu / DB / Invariant / Extraction / Config）共 ~25 个类 |

**不新增**任何 `__init__.py`（T-001 已建）；不动任何已有文件。

### 2.2 Out of Scope（明确不做）

| 不做 | 归属 ticket |
|:---|:---:|
| `memory_engine/types.py` pydantic 业务对象 | T-003 |
| `memory_engine/config.py` 常量 + Settings | T-003 |
| `scripts/validate_consistency.py` | T-003（schema.sql 与 models.py 都就位后才有意义） |
| `migrations/versions/0001_initial_schema.py` | T-004（用 alembic 包装 schema.sql） |
| `migrations/versions/0002_add_pgvector_ext.py` | T-004 |
| `memory_engine/utils/llm_gateway.py` 等 | T-005 |
| M1–M7 业务模块 | T-006 |
| 单元测试覆盖（`tests/unit/test_models.py` 等） | T-003（types.py 完成后写一次性单测） |

### 2.3 预算豁免

| 维度 | 上限 | 本 ticket | 豁免理由 |
|:---|:---:|:---:|:---|
| 代码行数 | ≤ 500 | ~570 | schema.sql + ORM 是**数据契约的双胞胎**（CLAUDE.md §2.4 强制 1:1）；拆分会让验证 / review 反而难，且单文件 < 300 行；超出 14% 在可接受范围 |
| 文件数 | ≤ 5 | 3 | 不超 |
| LLM 调用 | ≤ 50 | 0 | 纯模板生成 |
| 测试时长 | ≤ 60s | < 5s | 不超 |

---

## 3. 关键决策

### D12：ORM 风格 = `Mapped[Type] + DeclarativeBase`（SQLAlchemy 2.0 现代式）

```python
class DecisionModel(Base):
    __tablename__ = "decisions"
    decision_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # ...
```

不用 `MappedAsDataclass`（避免 dataclass kwargs init 复杂性）；不用 classic Column-style（legacy）。

### D13：异常类形态 = 富化版（含 `trace_id` + `extra` + 自定义 `__str__`）

依 04-ENGUIDE §8.11 强制要求："所有 `MemoryEngineError` 子类必须有 `trace_id` 属性（便于日志关联）"。模板：

```python
class MemoryEngineError(Exception):
    def __init__(self, trace_id: str = "", extra: dict[str, Any] | None = None) -> None:
        self.trace_id = trace_id
        self.extra = extra or {}
        super().__init__(self.__str__())

    def __str__(self) -> str:
        cls = type(self).__name__
        return f"[{cls} trace={self.trace_id}] {self.extra}" if self.extra else f"[{cls} trace={self.trace_id}]"
```

### D14：`schema.sql` 单文件（不切 `01_enums.sql / 02_tables.sql / ...`）

理由：(1) `validate_consistency.py`（T-003）读单文件解析更简；(2) 答辩展示一份 SQL 比一打文件清楚；(3) 当前 < 300 行，没必要拆。

### D15：`updated_at` 由 PG `BEFORE UPDATE` TRIGGER 维护（仅 3 张表用）

03-SCHEMA §3.1 明示。`decisions` / `card_quota` / `users` 三张表加 trigger；其他表只有 `created_at` 不需要。

### D16：`schema.sql` 头部 `CREATE EXTENSION IF NOT EXISTS vector;`

依赖 docker-compose 用的 `pgvector/pgvector:pg16` 镜像（已锁）；非该镜像跑该 SQL 会缺扩展。

---

## 4. 文件大纲

### 4.1 `schema.sql`（~260 行）

```
-- 头部：CREATE EXTENSION + 时区设置
-- §1 ENUMs（6 个）：provenance / evolution_type / decision_state / card_type / card_status / card_response
-- §2 触发器函数：update_updated_at()
-- §3 主表（按 FK 依赖顺序）：
--     users → decisions → decision_embeddings → card_quota → cards → reflect_logs → trace_log → decay_calculations
-- §4 索引（22 个）
-- §5 注释（COMMENT ON TABLE / COLUMN，便于 psql \d 查看）
```

### 4.2 `memory_engine/models.py`（~200 行）

```
- 顶部：import + Base = DeclarativeBase
- Enum 类（Python 端 6 个，与 SQL enum 1:1）
- 8 个 ORM Model 类（按 schema.sql 顺序）：
    UserModel / DecisionModel / DecisionEmbeddingModel / CardQuotaModel
    CardModel / ReflectLogModel / TraceLogModel / DecayCalculationModel
- 每个 Model 类：
    Mapped[Type] 字段声明（含 default、nullable、ForeignKey）
    __table_args__：CheckConstraint + Index 列表
    relationship()：自引用（decisions.parent）+ 跨表（如 cards → decisions）
```

### 4.3 `memory_engine/exceptions.py`（~110 行）

```
- MemoryEngineError 根类（含 trace_id / extra / __str__）
- LLMError / LLMQuotaExceededError / LLMTimeoutError / LLMResponseInvalidError
- FeishuError / FeishuAPIError / FeishuTraceLogError / FeishuRateLimitError
- DBError / DBQueryError / DBConsistencyError
- InvariantViolation / W2Violation / W13Violation / W14Violation
- ExtractionError / ExtractionTimeoutError / InvalidDecisionAtomError
- ConfigError
（共 ~25 个类，对齐 04-ENGUIDE §8.11 异常树图）
```

---

## 5. DoD（完成判定）

- [ ] 3 个文件已创建，行数 ±20% 内
- [ ] `psql -f schema.sql` 在 fresh PG 容器上零错误执行
- [ ] `\dt` 显示 8 主表 + 1 向量表（共 9）；`\dT+` 显示 6 enums
- [ ] `SELECT extname FROM pg_extension WHERE extname='vector';` 返回 vector
- [ ] Python `from memory_engine.models import *` 不报错；每个 Model 可 instantiate（无需 commit）
- [ ] Python `from memory_engine.exceptions import *` 不报错；各异常类可 instantiate；`__str__` 输出含 trace_id
- [ ] `mypy --strict` 在 `memory_engine/models.py` 与 `memory_engine/exceptions.py` 上**全过**（不走 exclude）
- [ ] `pre-commit run --all-files` 全过
- [ ] `pytest -q` 仍 0 测试 exit 0（T-003 才加首批单测）
- [ ] PR 描述含：LLM 调用次数（= 0）、3 文件清单、超预算豁免说明
- [ ] PROGRESS.md 追加 Day 9 T-002 完成条目

---

## 6. 风险

| 风险 | 应对 |
|:---|:---|
| **W2 CHECK 约束写错**（最关键不变量在 DB 层） | 单独冒烟测试：`INSERT INTO decisions ... (evolution_type='ROOT', parent_id=<uuid>)` 应抛 CHECK violation |
| **schema.sql ↔ models.py 漂移** | 本 ticket 由人工眼审；T-003 加 `validate_consistency.py` 自动化 |
| **enum 在 Python 与 SQL 间名称不一致** | Python 端 enum 值用 `str` 类型 + `value = "USER_STATED"` 与 SQL enum literal 严格对齐 |
| **mypy --strict 在 SQLAlchemy 2.0 类型上炸** | 用 `Mapped[Type]` 标准模式；遇到 `relationship()` 类型不全时加 `# type: ignore[attr-defined]` 局部豁免 |
| **pgvector 列类型在 mypy 下识别问题** | `pgvector` 已在 `pyproject.toml [[tool.mypy.overrides]] ignore_missing_imports = true` 名单内 |

---

## 7. 建议未来（不在本 ticket）

- `tests/unit/test_models.py` 单测每张表 instantiate + 关系正确（→ T-003）
- `tests/integration/test_int_schema.py` 用 testcontainers PG 跑整套 SQL（→ T-003）
- ORM 层加 `audit_log` 中间件（→ v1 后期，不是 17 天范围）
- pydantic 业务对象 ↔ ORM 互转 helpers（→ T-003）

---

## 8. 执行后用户验证步骤（在 WSL 里）

```bash
cd ~/FeishuAI-STZ
git pull origin main

# 1) schema.sql 灌进 PG
docker compose exec -T postgres psql -U memory -d memory < schema.sql
# 期望：CREATE EXTENSION / CREATE TYPE × 6 / CREATE TABLE × 9 / CREATE INDEX × 22 / CREATE TRIGGER × 3，无 ERROR

# 2) PG 端结构核查
docker compose exec -T postgres psql -U memory -d memory -c "\dt"      # 8 主表 + decision_embeddings
docker compose exec -T postgres psql -U memory -d memory -c "\dT+"     # 6 enums

# 3) ORM 冒烟
uv run python -c "from memory_engine.models import DecisionModel, Provenance, EvolutionType, DecisionState; print('OK')"

# 4) 异常树冒烟
uv run python -c "from memory_engine.exceptions import MemoryEngineError, W14Violation; e = W14Violation(trace_id='t1', extra={'user': 'u1'}); print(repr(e))"

# 5) W2 CHECK 约束验证（应抛 CHECK violation）
docker compose exec -T postgres psql -U memory -d memory \
  -c "INSERT INTO decisions (decision_id, subject, predicate, object, logical_timestamp, provenance, confidence, evolution_type) VALUES (gen_random_uuid(), 's', 'p', 'o', now(), 'USER_STATED', 0.9, 'SUPERSEDES');"
# 期望：ERROR 'evolution_type 与 parent_id 不一致'（W2 强制）

# 6) 既有验证仍全过
uv run pre-commit run --all-files
uv run pytest -q
```

任一步报错 → 立即停下，把错误输出贴回来，我修。

---

> **状态**：📝 草稿 · 待用户审定 · 审通过后我立即生成 3 个文件 + commit + push（自 Windows 端，避免 WSL push credential 问题）。
> **生成顺序**：schema.sql → exceptions.py → models.py（前者建立契约，后者依赖前者的 enum 与 CHECK 语义）
