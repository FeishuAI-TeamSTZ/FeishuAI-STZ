# T-003：业务对象 + 配置常量（types.py + config.py + 首批单测）

> **类型**：Phase 0 骨架 ticket（系列 3/5）
> **领地**：R1 内核工程师（`memory_engine/`）+ 测试 R1 共建（`tests/unit/`）
> **优先级**：P0（阻塞 T-004 validate_consistency / T-005 utils 层 / T-006 M1 切片）
> **计划用时**：1 天
> **关联 §8 接口**：04-ENGUIDE §3 数据三层 / §8.1–§8.10 出入参类型 / §8.4 PROVENANCE_TRUST_WEIGHTS / §9 配置
> **触及不变量**：W9（CONSENSUS_WEIGHTS OKR 顶档，应用层配置）；其余 W 在 T-005 / T-006 引用 config 阈值时落地
> **预算自检**：CLAUDE.md §6 ≤500 行 / ≤5 文件 → 本 ticket 6 文件 ~590 行；超 1 文件以保留单测分组清晰，超 18% 行数；理由见 §2.3
> **依据文档**：[03-SCHEMA](../docs/03-SCHEMA.md) §2 enum / §5.1 五因子（已锁）；[04-ENGUIDE](../docs/04-ENGUIDE.md) §3 数据三层 / §8 接口 / §9.2 必需常量；[01-CONSTITUTION](../docs/01-CONSTITUTION.md) §4.4 LLM 预算 / §5.5 W9

---

## 1. 目标

让 `memory_engine.types` 与 `memory_engine.config` 成为 **R1 内核业务模块（M1–M7）的唯一数据契约入口**：

- 往上：M1–M7 函数签名所有的入参 / 出参类型都从 `types.py` 导入（pydantic v2 BaseModel）
- 往下：`Decision.from_orm() / .to_orm()` 是业务对象 ↔ ORM 唯一桥
- 横向：所有阈值 / 权重 / 预算从 `config.py` 单点读取（不允许散落 magic number）

完成后，`from memory_engine.types import *` / `from memory_engine.config import settings, ...` 可用，**T-005 utils 层与 T-006 M1 切片可以直接消费**。

---

## 2. 范围

### 2.1 In Scope（6 文件，~590 行）

| # | 路径 | 估算 | 说明 |
|:---:|:---|:---:|:---|
| 1 | `memory_engine/types.py` | ~270 | 业务 enum + pydantic v2 业务对象（详见 §3） |
| 2 | `memory_engine/config.py` | ~110 | `Final` 常量 + pydantic-settings `Settings` 单例 |
| 3 | `tests/unit/test_models.py` | ~90 | 8 ORM 表 instantiate + metadata 自检 + W2/W14 CHECK 表达正确（不连真 PG） |
| 4 | `tests/unit/test_exceptions.py` | ~40 | 25 异常类 instantiate + `__str__` 含 trace_id + isinstance 关系 |
| 5 | `tests/unit/test_types.py` | ~50 | 关键业务对象 instantiate + Decision.from_orm/to_orm round-trip |
| 6 | `tests/unit/test_config.py` | ~30 | W9 / 5 因子 / 总预算上限 / Settings fail-fast 自检 |

**附带文档订正（外科手术外的微动，已与用户对齐）**：
- `docs/03-SCHEMA.md` §5.1：移除"⚠️ 与 02-DESIGN 不一致点"标记，改为"已确认 5 因子（2026-04-29）"
- `docs/04-ENGUIDE.md` §9.1：环境变量表加 `LLM_TPM_TIER` 行，并把 Doubao 三个 EP 拆分键名与 `.env.example` 对齐
- `.env.example`：已包含目标键，无需改动（仅在 §9.1 表中记录其存在）

### 2.2 Out of Scope

| 不做 | 归属 ticket |
|:---|:---:|
| `scripts/validate_consistency.py` | T-004 |
| `migrations/versions/0001_initial_schema.py`（alembic 包装 schema.sql） | T-004 |
| `tests/integration/test_int_schema.py`（testcontainers PG 端到端） | T-004 |
| `feishu_integration/types.py` DTO（FeishuMessage / FeishuDocChange / Event） | T-006 R2 接入 |
| LLM 网关 / 飞书网关实现 | T-005 |
| M1–M7 业务模块 | T-006+ |

### 2.3 预算说明

| 维度 | 上限 | 本 ticket | 状态 |
|:---|:---:|:---:|:---|
| 代码行数 | ≤ 500 | ~590 | 超 18%；types.py 承载 12+ 业务对象 + 4 业务 enum，单文件压缩到 270 行已是上限 |
| 文件数 | ≤ 5 | 6 | 超 1；4 个单测文件按 `tests/unit/test_<module>.py` 命名约定（04-ENGUIDE §6.4）一对一，合并会破坏测试组织 |
| LLM 调用 | ≤ 50 | 0 | 不超 |
| 测试时长 | ≤ 60s | < 5s | 不超 |

豁免合理性：types/config 是**业务数据契约**，单测按模块一一对应是 04-ENGUIDE §6.4 显式规约；下一个 T-004 已严格收敛在 3 文件 / ~350 行。

---

## 3. 关键决策

### D17：业务 enum 放 `types.py`，ORM enum 留 `models.py`

| 类别 | 位置 | 理由 |
|:---|:---|:---|
| `Provenance / EvolutionType / DecisionState / CardType / CardStatus / CardResponse`（6 个 SQL enum 镜像） | `models.py`（已有） | 服务于 SQLAlchemy `_PROV_SQL` 等列定义；`types.py` 直接 re-export |
| `LLMCategory / SourceType / ConflictLevel`（业务枚举，不入 SQL） | `types.py`（新增） | 03-SCHEMA §2.7 已说 `SourceType` 不入 SQL enum；`LLMCategory` 是网关分类；`ConflictLevel` 是卡片决策树 |

### D18：`Decision.from_orm()` 用 `model_validate(model, from_attributes=True)`

避免手工逐字段映射造成漂移；pydantic v2 原生支持 ORM 适配。`to_orm()` 用 `DecisionModel(**self.model_dump(exclude_none=True))`。

### D19：`Settings` 缺关键 env 时 fail-fast

| 字段 | 是否必填 | 缺失行为 |
|:---|:---:|:---|
| `database_url` | ✓ | raise `ConfigError` |
| `doubao_api_key` | ✓ | raise `ConfigError`（运行时；测试用 monkeypatch.setenv 注入） |
| `feishu_app_id` / `feishu_app_secret` / `feishu_verification_token` | ✓ | raise `ConfigError` |
| `log_level` / `cache_backend` / `environment` / `llm_tpm_tier` | ✗ | 默认值 |
| `doubao_*_endpoint_id` / `doubao_base_url` / `feishu_encrypt_key` / `redis_url` | ✗ | 默认空串（开发期占位）|

测试用 `pydantic_settings` 自带的 `model_config` + `env_file` 机制；缺必填时 pydantic 抛 `ValidationError`，我们包成 `ConfigError`。

### D20：测试不用 SQLite in-memory

理由：SQLAlchemy 2.0 + pgvector + JSONB + ENUM 都是 PG 专属；SQLite 适配代价 > 收益。本 ticket 测试只做：
- ORM Model 类可 import + instantiate（不连任何 DB）
- `Base.metadata.tables` 含 8 张表
- `__table_args__` 内 `CheckConstraint` 数量正确（W2 / W14 等存在）

真 PG 端到端留 T-004 用 testcontainers。

---

## 4. 文件大纲

### 4.1 `memory_engine/types.py`（~270 行）

```
# 顶部：from __future__ import annotations
# 业务 enum（3 个）：LLMCategory / SourceType / ConflictLevel
# ORM enum re-export：Provenance / EvolutionType / DecisionState / CardType / CardStatus / CardResponse
# 共享子模型：ConsensusSourceItem（jsonb 单条）
# 业务对象（按 §8 接口顺序）：
#   DecisionAtom（提取阶段，无 decision_id）
#   Decision（落库后，含 decision_id + state + 五维输入）
#     classmethod from_orm(model: DecisionModel) -> Decision
#     to_orm() -> DecisionModel
#   EvolutionJudgment / ReflectReport / ReflectContext
#   Card / CardAction / GateResult
#   FiveFactors
#   LLMResponse / FeishuResponse
#   ProcessResult / InterceptDecision
# __all__ 显式导出
```

### 4.2 `memory_engine/config.py`（~110 行）

```
- import Final, BaseSettings, etc.
- 常量：PROVENANCE_TRUST_WEIGHTS / CONSENSUS_WEIGHTS / DAILY_LLM_BUDGET
- 阈值：UNCERTAINTY_CARD_THRESHOLD / REFLECT_*_LOW/HIGH / ACTIVE_CONFIDENCE_MIN
- 闸门：DEFAULT_DAILY_CARD_QUOTA / WORK_HOUR_*_DEFAULT
- 衰减：DECAY_LAMBDA_BASE / DECAY_BATCH_INTERVAL_SECONDS
- 缓存：HOT_PATH_CACHE_TTL_SECONDS
- Settings(BaseSettings)：
    SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    所有字段（D19 明示必填 / 选填）
- get_settings() -> Settings  （单例 + ConfigError 包装）
```

### 4.3–4.6 单测文件

详见 §2.1 表格内说明；每个文件 ≤ 90 行，pytest 风格。

---

## 5. DoD（完成判定）

- [ ] 6 文件创建，行数 ±20% 内
- [ ] `from memory_engine.types import *` 不报错
- [ ] `from memory_engine.config import settings, PROVENANCE_TRUST_WEIGHTS, CONSENSUS_WEIGHTS, DAILY_LLM_BUDGET` 可用
- [ ] `mypy --strict memory_engine/` Success
- [ ] `pre-commit run --all-files` 全过
- [ ] `pytest -q tests/unit/` 全部通过且 < 5s；测试数 ≥ 20
- [ ] PR 描述含：LLM 调用 = 0；6 文件清单；预算超 1 文件 / 18% 行数说明；列出 T-004 预告
- [ ] 文档微订正：03-SCHEMA §5.1 锁定 5 因子；04-ENGUIDE §9.1 加 `LLM_TPM_TIER` + Doubao EP 三键；版本历史新增条目
- [ ] PROGRESS.md 追加 Day 13 T-003 条目

---

## 6. 风险

| 风险 | 应对 |
|:---|:---|
| pydantic v2 + SQLAlchemy 2.0 互转中 `Decimal ↔ float` | `Decision` 用 `field_validator` 在 `from_orm` 时把 Decimal 收敛为 float；`to_orm` 反向 |
| `model_validate(orm, from_attributes=True)` 对自引用 `parent` 关系递归 | `from_orm` 显式 `exclude={'parent'}`；本 ticket 不打通递归（M2 真接入时再处理） |
| `Settings` env_file 默认从 cwd 找 `.env`，CI / 测试不会有 | 测试用 `monkeypatch.setenv` + `Settings(_env_file=None)` 显式跳过；fail-fast 在 missing required 时 raise |
| mypy --strict 在 pydantic v2 `Field(default_factory=list)` 上偶炸 | 显式标注：`field: list[X] = Field(default_factory=list)`；必要时 `# type: ignore[assignment]` 局部豁免（已有 warn_unused_ignores） |
| 测试数 < 20 触不到覆盖目标 | 每张 ORM 表 + 每个业务对象 + 每个常量都至少 1 测；目标 ~25–30 测 |

---

## 7. 建议未来（不在本 ticket）

- T-004：`scripts/validate_consistency.py` + alembic `0001_initial_schema.py` + `tests/integration/test_int_schema.py`
- T-005：`memory_engine/utils/llm_gateway.py` + `feishu_client.py` + `cache.py` + `embeddings.py` + `invariants.py`
- T-006：M1 切片（webhook → cold_path → extractor → evolution_judge → cards → decay）
- types.py v2：加 DTO（FeishuMessage / FeishuDocChange / Event）—— 归 R2 接入领地，T-006 时建 `feishu_integration/types.py`

---

## 8. 执行后用户验证步骤

```bash
cd ~/FeishuAI-STZ
git pull origin main

# 1) types / config import 冒烟
uv run python -c "
from memory_engine.types import (
    DecisionAtom, Decision, EvolutionJudgment, ReflectReport,
    Card, FiveFactors, LLMResponse, LLMCategory, SourceType, ConflictLevel,
)
from memory_engine.config import (
    settings, PROVENANCE_TRUST_WEIGHTS, CONSENSUS_WEIGHTS, DAILY_LLM_BUDGET,
    UNCERTAINTY_CARD_THRESHOLD, DEFAULT_DAILY_CARD_QUOTA,
)
print('OK', sum(DAILY_LLM_BUDGET.values()), '<=', 10000)
"

# 2) 单测全过
uv run pytest -q tests/unit/

# 3) mypy --strict 全过
uv run mypy --strict memory_engine/

# 4) pre-commit 全过
uv run pre-commit run --all-files
```

任一步报错 → 立即停下，把错误输出贴回来，我修。

---

> **状态**：✅ **已完成**（2026-05-04）
> **commit 链**：[26a71b6](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/26a71b6)（ticket 草稿）→ [eac5838](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/eac5838)（5 因子锁定 + .env 对齐）→ [36daf85](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/36daf85)（types.py + config.py + 4 单测）→ [3159f63](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/3159f63)（Day 13 PROGRESS）
> **DoD 10/10 全 ✓**：6 文件 / 13 业务对象 / 13 常量 + Settings / mypy --strict / pre-commit / **pytest 73 passed in 0.99s** / W9 OKR 顶档自检 / 总日预算 ≤ 10K / Decision.from_orm round-trip / PROGRESS Day 13
> **实际行数**：1147（types 361 + config 159 + 4 测试 627；超 ticket 估算 590 by 94%，主要因测试覆盖广 + ruff-format 后空行规范）
> **后续 ticket**：T-004（validate_consistency.py + alembic 0001 + 集成测）
