# 工作记录 (PROGRESS.md)

> 项目过程证据；**按日倒序追加**。
> 格式与纪律见 [CLAUDE.md §2.8](./CLAUDE.md)。
> Day 1 = 2026-04-22（飞书 AI 校园挑战赛开赛日）；Day 23 = 2026-05-14（决赛日）。

---

## 2026-05-06 · Day 15 · T-004 漂移检查 + Alembic + 集成测落地（Phase 0 4/5）

### 改动

- 新建 [scripts/validate_consistency.py](./scripts/validate_consistency.py)（~250 行）：正则解析 schema.sql + introspect Base.metadata → 6 维度 1:1 比对（表名 / 字段 / enum 取值 / 命名 CHECK 单向 / 命名索引带白名单 / FK 引用关系）；exit 0/1 + stderr 报告；可作 module 调用（`from scripts.validate_consistency import check`）
- 新建 [migrations/versions/0001_initial_schema.py](./migrations/versions/0001_initial_schema.py)（49 行）：D22 `op.execute(schema.sql)` 整文件包装 + downgrade 反向 DROP（不动 EXTENSION vector）
- 新建 [tests/integration/test_int_schema.py](./tests/integration/test_int_schema.py)（137 行）：testcontainers PG 16 + pgvector → alembic upgrade head → validate.check() + pgvector 扩展 + W2 正负 + W14 负 共 5 集成测；`@pytest.mark.integration` 默认跳；fixture 含 `engine.dispose()` teardown 释放连接池
- 修订 `migrations/env.py`：`target_metadata = Base.metadata`（启用 alembic autogenerate）
- 修订 `.pre-commit-config.yaml`：取消注释 validate-consistency local hook（`uv run python scripts/validate_consistency.py`）
- 修订 `pyproject.toml [tool.pytest.ini_options].addopts`：加 `-m "not integration"`（开发期 default 跳集成测）
- 文档同步：CLAUDE.md §2.4 移除 "T-XXX 启用" 时序标注；docs/03-SCHEMA.md 附录 A 加 "✅ T-004 启用" 状态行
- T-003 ticket 状态行补完："📝 草稿" → "✅ 已完成 + commit 链 + DoD 10/10"
- T-004 ticket 状态行：草稿 → 已完成 + commit 链 d3b402e → e0a9f93 → 77f7242

### Commit 链（3 个）

1. `d3b402e ticket: T-004 ...（草稿审定）` — Day 14 已 commit
2. `e0a9f93 feat(T-004): validate_consistency.py + alembic 0001 + 集成测 + pre-commit hook` — 5 文件实现 + 4 文件修订
3. `77f7242 fix(T-004): 类型修复 + SIM117 + engine.dispose` — 3 处 mypy + 2 处 SIM117 + fixture teardown 显式释放

### DoD 8/8 验收

| # | 项 | 结果 |
|:---:|:---|:---|
| 1 | `validate_consistency.py` 静态干跑 | ✅ exit 0（OK: schema.sql ↔ memory_engine/models.py 一致） |
| 2 | `alembic upgrade head` 在 fresh PG | ✅ testcontainers PG 16 + pgvector 容器灌入零错误 |
| 3 | `pytest -q`（unit 仍 73 passed） | ✅ 73 passed in <2s（不收集集成测） |
| 4 | `pytest -m integration` | ✅ **5 passed in 5.48s** |
| 5 | `pre-commit run --all-files` | ✅ ruff-format / ruff / mypy / yaml / toml / merge / large-file / line-ending / **validate-consistency** 全过 |
| 6 | `mypy --strict` 在 scripts + tests/integration | ✅ Success: no issues found in 1 source file |
| 7 | **故意漂移自检** | ✅ 注入 UserModel.fake_field → exit 1 + stderr "只在 ORM.users.fields: fake_field" / `git checkout` 还原 → exit 0 |
| 8 | CLAUDE §2.4 + 03-SCHEMA 附录 A 更新 | ✅ 同步 inline |

### 卡壳与破局

| 问题 | 破局 |
|:---|:---|
| **首次 validate 报 14 处假漂移**：(1) 多行 CHECK 内 `AND parent_id IS NOT NULL` 被当字段；(2) ORM 给匿名 SQL CHECK 起了名（chk_decisions_confidence 等 11 处）；(3) idx_decisions_fts / idx_emb_hnsw 在 ORM 不可表达 | 三层修复（按 T-004 §3 D21 "95% 覆盖 + 兜底"）：(1) FIELD_LINE regex 加 SQL_TYPE_KEYWORD 兜底（uuid/varchar/numeric 等）；(2) named_checks 改单向比对（schema → ORM 必须存在；ORM 可以多）；(3) SQL_ONLY_INDEX_ALLOWLIST = {idx_emb_hnsw, idx_decisions_fts} |
| `uv sync --reinstall`（无 `--extra dev`）把 mypy/pytest 卸了 | `uv sync --extra dev` 重装；下次直接 `uv sync --extra dev` 不省 `--extra dev` |
| `mypy --strict` 在 validate_consistency.py 报 3 处 | `dict[str, type[Enum]]` + `dict[str, dict[str, Any]]` + `dict[str, set[str]]` 补全泛型参数；新加 `from enum import Enum` |
| `ruff` 报 SIM117（嵌套 with）2 处 | `pytest.raises(...)` + `pg_engine.begin() as conn` 合并到单 with 多 context（PEP 617 parenthesized 形式） |
| 集成测全过但 session cleanup 抛 `PytestUnraisableExceptionWarning`（psycopg `__del__` ResourceWarning + `filterwarnings=error` 升级） | fixture teardown 加 `engine.dispose()` 显式释放连接池；不污染 pyproject filterwarnings 全局规则 |
| 跨 Windows / WSL 文件 sync（每次 ruff/mypy 自动改) | 既有 `cp /mnt/e/...` 双向同步流程已稳定 |

### 决策（本日新锁定 / 复用）

- **D21 实施验证**（T-004 ticket 已锁）：正则 + ORM 兜底确实达 95% 覆盖；剩余 5%（多行 CHECK / 特殊索引）走 ALLOWLIST + 单向比对收口
- **D22 验证通过**：alembic 0001 = `op.execute(schema.sql)` 在 testcontainers fresh PG 跑通，downgrade 反向 DROP 也写好
- **D23 验证通过**：`pyproject addopts -m "not integration"` 默认跳；显式 `-m integration` 才跑（5.48s）
- **D24 验证通过**：validate 是脚本不是库；exit 1 + stderr；同时 export `check()` 函数供 module import
- **集成测 fixture 必须 engine.dispose()**：psycopg + create_engine + filterwarnings=error 三者交互需显式释放
- **Phase 0 推进**：1→2→3→4 完成，剩 T-005（utils 层）即 Phase 0 收官

### 遗留 / 下一步

- **下一个 ticket = T-005**（utils 层；R1 内核领地）：
  - `memory_engine/utils/llm_gateway.py` — Doubao 网关（heavy 2.0 / light 1.6 / embedding v1）+ TPM 计数器 + W12 降级 + trace_log 写入
  - `memory_engine/utils/feishu_client.py` — 飞书 API 网关（W13 强制 trace_log INSERT）
  - `memory_engine/utils/cache.py` — Hot Path 5min TTL 内存缓存（v1，cachetools）
  - `memory_engine/utils/embeddings.py` — Doubao Embedding v1 包装（1024 维）
  - `memory_engine/utils/invariants.py` — W2/W14/W15 运行时 assert
- **节奏估算**（决赛 Day 23 = 5/14；今日 Day 15）：8 天到 deadline → T-005 utils 2 天 + T-006 M1 切片 4 天 + benchmark 跑分 + 答辩准备 2 天
- **NPU-src 协作**：origin/test 分支仍未与 main 合流（其分支独立做 baseline RAG），用户需人工沟通

### LLM 调用

本日累计 0 次生产调用。Claude Code 协作约 ~30 轮（T-004 ticket 实施 + 14 处假漂移诊断与修复 + 集成测调试 + ResourceWarning 修 + 状态文档同步）。

---

## 2026-05-05 · Day 14 · T-003 push 完成 + T-004 ticket 草稿审定

### 改动

- T-003 4-commit 链推送至 origin（[26a71b6](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/26a71b6) → [eac5838](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/eac5838) → [36daf85](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/36daf85) → [3159f63](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/3159f63)）；WSL hard-reset 到 origin 收敛（WSL/Windows commit SHA 因 git am committer 时间重生成而不同，内容 `git diff` 验为空）
- 新建 [tickets/T-004-validate-consistency-and-alembic.md](./tickets/T-004-validate-consistency-and-alembic.md)（340 行）— commit [d3b402e](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/d3b402e)：5 文件 / ~320 行 / 预算内（无豁免）；DoD 强化（**故意漂移自检**：临时加字段 → exit 1 → 删除 → exit 0）

### 决策（本日新锁定，留待 T-004 实施期沿用）

- **D21 = (a)** SQL 解析用正则（不引入 sqlparse 等新依赖；schema.sql 结构稳定，正则覆盖 ~95% + ORM introspect 兜底）
- **D22 = (a)** alembic `0001_initial_schema.py` 用 `op.execute(schema.sql 整文件)`（单一真相源；不拆 alembic ops）
- **D23 = (b)** 集成测 `@pytest.mark.integration` + `pyproject.toml [tool.pytest.ini_options].addopts -m "not integration"` 默认跳；CI / 手工 `pytest -m integration` 显式跑
- **D24 = exit 1 + stderr**（`validate_consistency.py` 是脚本不是库；应用层需软调用走 `subprocess.run(...).returncode`）
- **commit 节奏复用**：T-002 / T-003 验证过的 "ticket-only commit 单独提" 模式继续——T-004 草稿单独 push（[d3b402e](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/d3b402e)），实施期再切 feat / fix / progress 链

### 卡壳与破局

| 问题 | 破局 |
|:---|:---|
| T-003 commit 3 在 pre-commit 阶段炸 2 次（ruff-format auto-modify + mypy 测试侧 5 错） | 一次性合修：(1) `.pre-commit-config.yaml` mypy `additional_dependencies` 加 `pytest>=8.0`；(2) test_models.py 用 `cast(Table, X.__table__)` 显式收窄（3 处）；(3) 删冗余 `# type: ignore[union-attr]`；合在 commit 3 内一并提，不再单独切 fix commit |
| `git am` 在 Windows 端被 working tree 已有的 untracked 文件挡 | `git stash --include-untracked` 安全网 → `git am` 干净 → `git push` → push 验证后 `git stash drop`（避免数据损失） |
| WSL local commit 与 origin（Windows `git am` 重生成）SHA 不同，但内容相同 | `git diff WSL_HEAD origin/main` 验空 → `git reset --hard origin/main` 收敛；4 commit 都验过 |

### 遗留 / 下一步

- **下一个 ticket = T-004 实施**（留下一会话）：
  - `scripts/validate_consistency.py`（~200）正则解析 + ORM introspect + 比对
  - `migrations/versions/0001_initial_schema.py`（~40）+ `migrations/env.py` 顺手把 `target_metadata = None` → `Base.metadata`
  - `tests/integration/test_int_schema.py`（~80）testcontainers PG → upgrade → validate → W2/W14 反向
  - `.pre-commit-config.yaml` 取消注释 validate-consistency local hook
  - `pyproject.toml` `addopts` 加 `-m "not integration"`
- **节奏（9 天到决赛 Day 14 → Day 23）**：T-004 1 天 → T-005 utils 层 2-3 天 → T-006 M1 切片 3-5 天 → benchmark 跑分余量
- **T-003 ticket 状态行待补**：T-003 ticket 末尾尚未加"✅ 已完成 + commit 链"块（沿 T-001 / T-002 模式）；T-004 实施时一并补

### LLM 调用

本日累计 0 次生产调用。Claude Code 协作约 ~30 轮（T-003 4-commit push + 漂移修复 + 验收 + T-004 ticket 起草 + 本节追写）。

---

## 2026-05-04 · Day 13 · T-003 业务对象 + 配置常量落地

### 改动

- 新建 [tickets/T-003-business-types-and-config.md](./tickets/T-003-business-types-and-config.md)（~150 行）：草稿 → 实施 → 验收（方案 B 路线：T-003 = types/config + 单测；T-004 留给 validate_consistency + alembic + 集成测）
- 新建 [memory_engine/types.py](./memory_engine/types.py)（361 行）：pydantic v2 业务对象层；3 业务专属 enum（LLMCategory / SourceType / ConflictLevel）+ ORM enum re-export + 共享子模型 ConsensusSourceItem + 13 业务对象（DecisionAtom / Decision / EvolutionJudgment / ReflectContext / ReflectReport / FiveFactors / Card / CardAction / GateResult / LLMResponse / FeishuResponse / ProcessResult / InterceptDecision）；`Decision.from_orm()`(model_validate from_attributes) + `to_orm()`(model_dump + jsonb 收敛) 是 ORM ↔ 业务对象唯一桥
- 新建 [memory_engine/config.py](./memory_engine/config.py)（159 行）：`Final` 常量层（PROVENANCE_TRUST_WEIGHTS / CONSENSUS_WEIGHTS / DAILY_LLM_BUDGET / 4 阈值 / 3 闸门 / 2 衰减 / 1 缓存 TTL）+ pydantic-settings `Settings`（5 必填 + 9 选填 env，对齐 04-ENGUIDE §9.1 v1.0.1）；`get_settings()` 包装 ValidationError → ConfigError
- 新建 [tests/unit/test_models.py](./tests/unit/test_models.py)（152 行）+ [test_exceptions.py](./tests/unit/test_exceptions.py)（109 行）+ [test_types.py](./tests/unit/test_types.py)（240 行）+ [test_config.py](./tests/unit/test_config.py)（126 行）：W9 / W2 / W14 / W13 在测试中显式断言；总日预算 ≤ 10K 自检；Decision.from_orm round-trip
- 文档微订正：
  - [docs/03-SCHEMA.md](./docs/03-SCHEMA.md) v1.0 → v1.0.1：§5.1 五因子从"⚠️ 需澄清"改为锁定声明（02-DESIGN v3.3.1 已对齐 5 因子）；附录 C 新增 v1.0.1 行
  - [docs/04-ENGUIDE.md](./docs/04-ENGUIDE.md) v1.0 → v1.0.1：§9.1 环境变量表与 `.env.example` 对齐（拆分 Doubao Heavy/Light/Embedding EP + DOUBAO_BASE_URL + LLM_TPM_TIER + ENVIRONMENT + REDIS_URL + FEISHU_ENCRYPT_KEY），加必填/选填两栏；附录 C 新增 v1.0.1 行
- `.env.example` 无需改动（已包含目标键）

### DoD 验收（10/10 全过）

| # | 项 | 结果 |
|:---:|:---|:---|
| 1 | 6 文件创建 | ✅ types 361 / config 159 / 4 测试合计 627（test_models 152 + test_exceptions 109 + test_types 240 + test_config 126）；总 1147 行业务+测试代码（超 ticket 估算 590 by 94%，主要因测试覆盖广 + ruff-format 后空行规范） |
| 2 | `from memory_engine.types import *` 不报错 | ✅ 13 业务对象 + 3 业务 enum + 6 ORM enum re-export 全部 importable |
| 3 | `from memory_engine.config import settings, ...` 可读 | ✅ 13 常量 + Settings + get_settings 全部 importable |
| 4 | `mypy --strict memory_engine/` Success | ✅ `Success: no issues found in 6 source files` |
| 5 | `pre-commit run --all-files` 全过 | ✅ ruff-format / ruff / mypy / yaml / toml / merge / large-file / line-ending 全过 |
| 6 | `pytest -q tests/unit/` 全过 | ✅ **73 passed in 0.99s**（test_models 20 + test_exceptions 26 + test_types 17 + test_config 13，含 parametrize 展开） |
| 7 | W9 OKR 顶档自检 | ✅ `OKR=0.40 > max(others)=0.30`（test_config.test_w9_okr_top_weight） |
| 8 | 总日预算 ≤ 10K | ✅ `sum(DAILY_LLM_BUDGET.values()) = 9500 ≤ 10000` |
| 9 | Decision.from_orm/to_orm round-trip | ✅ Decimal → float 收敛；UUID / 七字段 / state / evolution_type 全保留（test_types.test_decision_from_orm_round_trip） |
| 10 | PROGRESS.md 追加 Day 13 条目 | ✅ 即本节 |

### 决策（本日新锁定）

- **D17 = 业务 enum 放 types.py，ORM enum 留 models.py**：types.py re-export ORM enum，对外接口不再 import models（数据三层纪律）
- **D18 = `Decision.from_orm` 用 `model_validate(model, from_attributes=True)`**：避免手工逐字段映射；Decimal → float 用 `field_validator(mode="before")` 收敛
- **D19 = Settings fail-fast**：5 必填 env 缺失即 raise ConfigError（DATABASE_URL / DOUBAO_API_KEY / FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_VERIFICATION_TOKEN）
- **D20 = 单测不连真 PG**：ORM Model 只 instantiate + metadata 自检；端到端 SQL 端测留 T-004 用 testcontainers
- **5 因子永久锁定**（03-SCHEMA §5.1 ⚠️ 块清理）：02-DESIGN v3.3.1 已对齐，03-SCHEMA v1.0.1 同步声明
- **04-ENGUIDE §9.1 环境变量表与 .env.example 对齐**：拆分 Doubao 三档 EP + 新增 4 个开发期占位 env
- **预算超出说明**：T-003 1147 行 / 7 文件（超 500 by 129% / 超 5 by 2）；测试占 55%，单测分组按模块一对一是 04-ENGUIDE §6.4 显式规约（commit 3 实际带入 .pre-commit-config.yaml 一并修订，文件数从 6 调到 7）

### 卡壳与破局

| 问题 | 破局 |
|:---|:---|
| WSL `wsl --status` 输出乱码 + 一次 Hyper-V NAT 报错 | 重试 `wsl -d Ubuntu` 即恢复；非项目问题 |
| Windows 端无 uv（py.exe 仅 3.13，pyproject 锁 3.12） | 走 PROGRESS Day 8 验证过的 `/mnt/e` 直读模式：Windows Write 后 `cp /mnt/e/... ~/FeishuAI-STZ/...` 同步到 WSL，`uv run` 在 WSL 端跑（避免 format-patch 中转） |
| pydantic v2 + SQLAlchemy 2.0 互转 Decimal ↔ float | `field_validator(mode="before")` 在 Decision 类 import 时把 Decimal 转 float；test_decision_from_orm_round_trip 验通 |
| Settings type checking 在 pydantic-settings 3 上 mypy 报 `[call-arg]` | 局部 `# type: ignore[call-arg]`（warn_unused_ignores=true 下不会误报） |
| **pre-commit mypy hook 在测试文件上炸**（pytest 不在 hook venv → `@pytest.mark.parametrize` 被当 untyped 装饰器） | `.pre-commit-config.yaml` mypy `additional_dependencies` 加 `pytest>=8.0`；`uv run mypy memory_engine/` 之前过是因为只检 memory_engine/ 目录 |
| **SQLAlchemy 2.0 `DeclarativeBase.__table__` 类型为 `FromClause`**（无 `.columns` / `.indexes` 属性） | test_models.py 用 `cast(Table, X.__table__)` 显式收窄（3 处）；删冗余 `# type: ignore[union-attr]` |

### 遗留 / 下一步

- **下一个 ticket = T-004**（validate_consistency + alembic 包装 + 集成测）：
  - `scripts/validate_consistency.py` — 解析 schema.sql + introspect Base.metadata → 比对漂移
  - `migrations/versions/0001_initial_schema.py` — alembic 包装 schema.sql
  - `tests/integration/test_int_schema.py` — testcontainers PG 端到端
  - 启用 [CLAUDE.md §2.4](./CLAUDE.md) 第 4 步（pre-commit 已预留 entry）
- **commit 链待打**（本日只完成实施 + 测试 + 文档；尚未 commit；commit 节奏沿 T-002 的 4-commit 模式：ticket → 业务实现 → 文档订正 → 任何 fix）
- **DTO 推迟**（FeishuMessage / FeishuDocChange / Event）：归 R2 接入领地，T-006 时建 `feishu_integration/types.py`
- **T-003 测试未覆盖项**：Decision.parent 自引用 relationship 的递归 from_orm（M2 真接入时再处理；本 ticket 显式 exclude）

### LLM 调用

本日累计 0 次生产调用。Claude Code 协作约 ~12 轮（计划讨论 + ticket 草稿 + types/config 实施 + 4 单测 + 文档订正 + 验收）。

---

## 2026-05-01 · Day 10 · T-002 数据持久化层落地

### 改动

- 新建 [tickets/T-002-data-persistence-layer.md](./tickets/T-002-data-persistence-layer.md)（252 行）：草稿 → 审定 → 实施 → 验收
- 新建 [schema.sql](./schema.sql)（290 行）：6 enums + 8 主表 + 1 向量表 + 15 named indexes + W2 / W14 CHECK + 3 BEFORE UPDATE 触发器；与 [03-SCHEMA.md](./docs/03-SCHEMA.md) §3 1:1 镜像
- 新建 [memory_engine/models.py](./memory_engine/models.py)（437 行）：SQLAlchemy 2.0 `Mapped + DeclarativeBase` 风格；6 Python enum 类（与 SQL enum literal 严格 1:1）+ 8 ORM 模型类；自引用 parent + JSONB consensus_sources + Vector(1024) embedding；mypy --strict 全过
- 新建 [memory_engine/exceptions.py](./memory_engine/exceptions.py)（121 行）：`MemoryEngineError` 根类（trace_id + extra + 自定义 `__str__`）+ 25 子类（LLM / Feishu / DB / Invariant / Extraction / Config 共 6 大类）；对齐 [04-ENGUIDE §8.11](./docs/04-ENGUIDE.md)

### Commit 链（4 个）

1. `ef23650 ticket: T-002 数据持久化层（草稿审定）` — ticket doc 单独 commit（沿用 T-001 模式）
2. `0ddb720 feat(T-002): schema.sql + ORM models + 异常树` — 3 个文件实现
3. `4669a25 fix(T-002): 移除冗余 type:ignore` — mypy 报 `unused-ignore`（pyproject 已全局 ignore pgvector）
4. `4ff6042 chore(T-002): pre-commit ruff-format auto-fixes` — ruff-format 重排（48 处行长 + import 拆分）；走 WSL → format-patch → Windows 应用 → push

### DoD 验收（8/8 全过）

| # | 项 | 结果 |
|:---:|:---|:---|
| 1 | `psql -f schema.sql` 在 fresh DB 灌入 | ✅ 零错误 |
| 2 | enum / table / index / trigger / extension | ✅ 6 enums × (type+array)=15 / 8 表 / 23 indexes / 3 triggers / pgvector 0.8.2 |
| 3 | ORM import + 8 表注册 + 6 enum 值列举 | ✅ `Base.metadata.tables` = 8；enum 值与 SQL 严格对齐 |
| 4 | 异常树冒烟（trace_id / extra / __str__） | ✅ 25 子类全可 instantiate；`LLMQuotaExceededError(trace_id="trc_abc", extra={...})` 输出 `[LLMQuotaExceededError trace=trc_abc] {'category': 'EVOLVE_HEAVY', 'used': 3050}` |
| 5 | **W2 CHECK 负样本** | ✅ `INSERT ... evolution_type='SUPERSEDES', parent_id=NULL` 抛 `chk_decisions_evolution_parent` violation |
| 6 | W2 CHECK 正样本 | ✅ ROOT 决策插入成功，state=ACTIVE / confidence=0.95 |
| 7 | **W14 CHECK 负样本** | ✅ `INSERT card_quota count=6, max_daily=5` 抛 `chk_card_quota_count` violation |
| 8 | mypy --strict / pre-commit / pytest | ✅ `Success: no issues found in 4 source files` / 全过 / `no tests ran in 0.02s` |

### 卡壳与破局

| 问题 | 破局 |
|:---|:---|
| **mypy `unused-ignore` 报错** | `# type: ignore[import-untyped]` 在 pgvector import 上是冗余（pyproject `[[tool.mypy.overrides]]` 已全局 `ignore_missing_imports`）→ 删除局部注释 |
| **ruff-format 在 WSL 端 auto-fix 48 处** | 走 T-001 验证过的 format-patch 模式：WSL commit → `git format-patch -o /mnt/e/wsl-patches/` → Windows `git am` → Windows push → WSL pull |
| **Docker Desktop WSL 集成偶尔断** | 用户重启即可恢复；非项目问题 |
| **mypy informational：unused module overrides** | `apscheduler.* / cachetools.* / testcontainers.*` 三个 overrides 未触发 import → T-005 接入 utils 时自然消化，不修 |

### 决策（本日新锁定）

- **D12 = SQLAlchemy 2.0 `Mapped + DeclarativeBase`**（不用 MappedAsDataclass / 不用 Classic Column）
- **D13 = 异常类含 `trace_id + extra + __str__`** —— 满足 04-ENGUIDE §8.11 "trace_id 属性必须" 强制要求
- **D14 = schema.sql 单文件**（不切 01_enums.sql / 02_tables.sql 等）
- **D15 = `BEFORE UPDATE` TRIGGER 仅 3 张表用**（users / decisions / card_quota）
- **D16 = `CREATE EXTENSION vector` 在 schema.sql 头部**（与 docker-compose `pgvector/pgvector:pg16` 镜像锁定）
- **W2 / W14 在 DB 层强制**：跑负样本验证，违反者 PG 直接 reject —— 这两条不变量**绝不会被 App bug 绕过**
- **预算豁免接受**：T-002 ~640 行（超 500 by 28%）；理由 schema↔ORM 是数据契约的双胞胎，拆分 review 反而难

### 遗留 / 下一步

- **下一个 ticket = T-003**（business types + config + consistency check）：
  - `memory_engine/types.py` — pydantic v2 业务对象（DecisionAtom / Decision / EvolutionJudgment / ReflectReport / Card / FiveFactors 等）
  - `memory_engine/config.py` — 常量（PROVENANCE_TRUST_WEIGHTS / CONSENSUS_WEIGHTS / DAILY_LLM_BUDGET / 阈值 / 闸门 / 衰减）+ pydantic-settings
  - `scripts/validate_consistency.py` — schema.sql ↔ models.py 漂移检查
  - `tests/unit/test_models.py` + `tests/unit/test_exceptions.py` — 首批单测（T-002 没写测试，T-003 补齐）
- **WSL git PAT 配置仍未做**：每次 push 走 format-patch 中转，可接受；T-005 启动前可考虑 GCM bridge
- **实际行数 vs ticket 估算偏差**：T-002 估算 570 → 实际 640（+12%）；schema/ORM 注释充分，可读性优先

### LLM 调用

本日累计 0 次生产调用。Claude Code 协作约 ~15 轮（schema 设计 + ORM 类型 + 异常树绘制 + DoD 验收 + 文档更新）。

---

## 2026-04-29 · Day 8 · NPU-src 整合 + T-001 项目基线落地 + meta-cleanup

### 早间 — NPU-src AB 测试框架整合（commit 418431f → a890dc0）

**背景**：NPU-src 在 commit `418431f` 推送了 AB 测试框架（TC001-TC009 + fixture），同时复活了已删除的 `ARCHITECTURE.md` / `METRICS.md`，且把 fixture 放在了 `tests/fixtures/`（与 04-ENGUIDE §1 不一致）。

**改动**（commit `a890dc0`）：
- `git pull` 拉下 418431f；选择整合方案 (A) —— 保留有价值产出，删除冗余
- 重新删除 `ARCHITECTURE.md` / `METRICS.md` / `TEST_CASES_AB.md`（被 v3.3 + 06-benchmark-design 取代）
- `git mv tests/fixtures/* → benchmark/fixtures/`（保留 history）
- `git mv tests/validate_fixtures.py → benchmark/validate_fixtures.py`（修 import 路径 + sys.path 兜底）
- 新建 `benchmark/__init__.py` + `benchmark/fixtures/__init__.py`
- 新建 [docs/06-benchmark-design.md](./docs/06-benchmark-design.md) v1.0（408 行）：基于 NPU-src TEST_CASES_AB 升级为标准化文档；TC001-TC009 + 评分规则 + fixture 契约 + 与宪法 §8 承诺值显式对照 + 与 04-ENGUIDE §8 接口一一映射
- [docs/01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) v1.2 → v1.3：§10.2 双贡献者结构 + §10.3 多人协作纪律重写 + §11 状态行 + 附录 B v1.3 行
- [CLAUDE.md](./CLAUDE.md) v1.2 → v1.3：§3.1 双贡献者 + 多人协作纪律落地

### 午间 — T-001 项目基线实施（WSL 内 c427a26 → 6f957ae）

**改动**（5 个 commit 链）：
1. `c427a26 feat(T-001): 项目基线 + 包结构（22 文件）` — pyproject.toml / .python-version / .env.example / .gitattributes / .pre-commit-config.yaml / alembic.ini / docker-compose.yml / migrations/env.py / conftest.py / 10 个 `__init__.py` / README.md（quick-start 段落）
2. `a69dbb1 fix(T-001): mypy exclude 加 benchmark/fixtures/ 与 validate_fixtures.py`
3. `fbdfac7 fix(T-001): validate_fixtures.py 加最小类型注解通过 mypy strict`
4. `1f6ac1a fix(T-001): pre-commit mypy exclude 加 validate_fixtures.py`
5. `6f957ae chore(T-001): pre-commit auto-fixes + uv.lock`

**T-001 DoD 全过 ✓**：
- `uv sync` 装齐 71 包
- `pre-commit run --all-files` 全过（ruff format / ruff check / mypy --strict / yaml / toml / merge / large-file / line-ending）
- `docker compose up -d postgres` → `feishu-memory-pg healthy`（端口 5432）
- pgvector **0.8.2** 已装（PG 16 + plpgsql 1.0 + vector 0.8.2）
- `pytest -q` 收集 0 个测试 exit 0
- `validate_fixtures` 加载 TC001 / TC002 数据 OK

### 晚间 — Meta-cleanup（自审后批量修订 14 处规约违反）

**改动**（一次性扫除文档体系内的隐性矛盾，不动业务代码）：
- 4 处 `Seed-2.0` 残留 → `Doubao`（宪法 §5.5 W12 / §8.3 降级 / 03-SCHEMA §9 W12 / 04-ENGUIDE §9.1 env var）
- 03-SCHEMA / 04-ENGUIDE 头部 `01-CONSTITUTION v1.1` → `v1.3`
- CLAUDE.md §0 阅读顺序加入 06-benchmark；§5 删除 05-edge（标 "待建"）
- CLAUDE.md §1.1 example 错引 W8 → 改 W2 演化关系不变量
- CLAUDE.md §2.4 schema 改动流程加 "T-002 / T-003 后启用" 时序标注
- CLAUDE.md §2.6 `requirements.txt` → `pyproject.toml` + `uv.lock`
- CLAUDE.md §4 升级触发项 `ADR` → `02-DESIGN / 03-SCHEMA / 04-ENGUIDE`
- 02-DESIGN 头部 date 行从"日记式长 parenthetical"瘦身为版本指针；新增"附录·修订历史"（v3.3 → v3.3.3 共 4 行）
- 02-DESIGN §二 资源前提行加 TPM 限定；§六 三大测试章前加 06-benchmark-design 链接
- 宪法 §4.4 标题加 TPM 限定（"约束底层 = TPM 1w 单人 / 3w 小组"）
- README 阅读顺序加 06 + 标 05 待建
- T-001 ticket 状态 `📝 草稿` → `✅ 已完成 + commit 链 + DoD ✓`
- PROGRESS.md 完整重写（即本文件）：消除"双 Day 8 + Day 6 夹中间"，按倒序 + 一日一条目重组，补出 Day 7

### 卡壳与破局

| 问题 | 破局 |
|:---|:---|
| **mypy --strict 把 NPU-src fixture 数据文件标红 7 处** | `[tool.mypy]` 加 exclude 列表 + pre-commit hook 同步 exclude；validate_fixtures.py 给 `types` 显式注解 |
| **`tool.uv.dev-dependencies` 在 uv 0.11 已废弃** | 改用 PEP 621 `[project.optional-dependencies]` dev 组（早先描述说 PEP 735 是术语口误） |
| **bash heredoc + WSL 透传时 `[[ ... ]]` 模式匹配崩** | 简化为 sleep + 直接验证，避免在 wsl bash -lc '...' 内嵌套复杂 bash 控制流 |
| **WSL 端 git push 卡 credential prompt（PAT 未存）** | format-patch 绕道：WSL `git format-patch` → `/mnt/e/wsl-patches/` → Windows `git am` 应用 → Windows push（凭据已存） → WSL `git pull` 同步回拉 |
| **Git Bash 的 MSYS_PATH_CONV 把 `/home/...` 改写成 `D:/Git/home/...`** | 全程 `MSYS_NO_PATHCONV=1 wsl -d Ubuntu -u zero -- bash -lc '...'` |
| **PROGRESS.md 时间线乱（双 Day 8 + Day 6 夹中间 + 缺 Day 7）** | 完整重写，按"倒序 + 一日一条目 + 子段早/午/晚"重组（即本次） |
| **WSL 14 小时未释放的僵尸 git push 进程树** | 定位 PID 331/865/866/867 → kill 干净；下次 push 前先用 `ps -ef` 自查 |

### 决策（本日新锁定）

- **整合方案 (A)**：保留 NPU-src 有价值产出（TC001/TC002 fixture v0.1 + TEST_CASES_AB 升级为 06），删除被 v3.3 淘汰的旧文档
- **NPU-src 子领地 = `benchmark/fixtures/`**（宪法 §10.2 v1.3）
- **mypy --strict 范围**：业务代码严管；benchmark/fixtures + validate_fixtures.py exclude（数据文件容许灵活）
- **uv 依赖组语法**：PEP 621 `[project.optional-dependencies]` dev 组（不是 PEP 735 dependency-groups）
- **WSL push 工作流**：当前阶段 WSL 端不存 PAT，用 format-patch 中转；下次 ticket 前可改用 GCM bridge

### 遗留 / 下一步

- **下一个 ticket = T-002**：写 `memory_engine/{models.py, types.py, exceptions.py, config.py}` + `schema.sql` + `scripts/validate_consistency.py`（首个真业务代码 ticket）
- **WSL git PAT 配置**：T-002 前可执行 `git config --global credential.helper '/mnt/c/Program\ Files/Git/mingw64/bin/git-credential-manager.exe'` 让 WSL 共享 Windows GCM
- **NPU-src 协作沟通**：建议告知他读 [04-ENGUIDE §1](./docs/04-ENGUIDE.md) 路径规约 + [01-CONSTITUTION §10.3](./docs/01-CONSTITUTION.md) 协作纪律（避免下次再复活旧文档）
- **TC003-TC009 fixture 待建**（T-005 阶段）；TC001 v0.1 100 噪声 → 赛事级 1000 条目标
- **pgvector Python binding 冒烟测试**：T-002 ORM 实现时验证

### LLM 调用

本日累计 0 次生产调用（全部为文档 + 项目骨架 + 工具链整合）。Claude Code 协作约 ~30 轮。

---

## 2026-04-28 · Day 7 · WSL 环境就绪 + 资源刷新 + T-001 ticket draft

### 改动

- [docs/01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) v1.1 → v1.2：§3.2 微调禁令理由更新；§3.3 加任务调度切换 Conditional Scope 行；§4.1 资源表全面刷新（Doubao 2.0/1.6 + Embedding v1，TPM 1w 单人 / 3w 小组）；§11 状态行；附录 B v1.2 行
- [docs/02-DESIGN.md](./docs/02-DESIGN.md)：`Seed-2.0` → `Doubao`（17 处）；header 加 LLM 命名口径段；§二 / §四 机制三 / §十一 全部 TPM-aware；§十一 任务调度行加 APScheduler v1 / Celery v2
- [docs/04-ENGUIDE.md](./docs/04-ENGUIDE.md) §4.4：LLM 调用预算表加"模型"列（Heavy=2.0 / Light=1.6 / Embedding 独立）+ TPM 网关强制行为
- WSL 环境探索 + 配置：Ubuntu 24.04.3 + Python 3.12.3 + Docker 29.1.5 + uv 0.11.8 装妥；git 身份与 Windows 端对齐（czhang076）
- C 盘空间问题识别（剩 9.3 GB）+ Docker Desktop disk image 迁到 `E:\Docker\DockerDesktopWSL`（释放 C 盘压力）
- [tickets/T-001-project-baseline.md](./tickets/T-001-project-baseline.md) 草稿创建（commit `e87504c`）

### 决策

- **D6 = (b)**：v1 任务调度 = APScheduler（同进程内存）；v2 切 Celery + Redis 触发条件入宪法 §3.3
- **D7 = (b)**：Python 3.12 锁定（pyproject.toml `requires-python = ">=3.12,<3.13"`）
- **D8 = (a)**：T-001 提供 `docker-compose.yml`（PG 16 + pgvector）
- **D9 = (a)**：Phase 0 完成后，第一个业务 ticket = M1 + M2 + M5 端到端切片
- **D11 = (b)**：包管理用 uv（不是 pip）—— 单二进制不需要 sudo + PEP 621 原生支持
- **隐含 D10**：Heavy 路径默认 Doubao 2.0，Light 路径默认 Doubao 1.6
- **资源命名口径**："Seed-2.0" 全部改为 "Doubao"
- **TPM 替代 calls/day**：约束底层是 TPM 1w 单人 / 3w 小组

### 遗留

- T-001 ticket 文档就位，等 WSL 环境验证后实施（→ Day 8 完成）
- 火山引擎 EP 实际数值待你认领后填入 `.env`（T-001 提供 `.env.example` 占位）

### LLM 调用

本日累计 0 次生产调用（全部为环境配置 + 文档刷新）。

---

## 2026-04-27 · Day 6 · 文档体系底座

### 改动

- [CLAUDE.md](./CLAUDE.md) v1.0 → v1.1：对齐 DESIGN.md v3.3（5 处：版本头 / §2.3 范围 / §2.6 依赖流程 / §3.1 角色 / §7 状态）；新增 §2.8 工作记录习惯
- 根目录 `DESIGN.md` → [docs/02-DESIGN.md](./docs/02-DESIGN.md)：3 处轻整理（头部加文档编号 + 引用宪法 / v3.1 → v3.3 / v3.2 → v3.3）
- 删除 `ARCHITECTURE.md`（旧试行版） + `METRICS.md`（旧指标体系）
- 新建 [docs/01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) v1.0 → v1.1（412 行）：11 主节 + 2 附录；§3.1.4 / §3.3 范围级修订纳入 D1/D4 决策
- 新建 [docs/03-SCHEMA.md](./docs/03-SCHEMA.md) v1.0（702 行）：8 主表 + 6 enum + 状态机 + W1-W15 落点映射
- 新建 [docs/04-ENGUIDE.md](./docs/04-ENGUIDE.md) v1.0（1096 行）：§8 接口契约总表覆盖 M1-M7 + 共享工具 + CLI 共 ~25 个函数签名
- [docs/02-DESIGN.md](./docs/02-DESIGN.md) §四 机制七 公式补 `× f_user_validation` 因子（与 03-SCHEMA 对齐）
- 新建 [PROGRESS.md](./PROGRESS.md) + [.gitignore](./.gitignore)

### 决策

- **范围**：v3.3 七大机制 + 三大主测试全部 in scope；方向 A / C 核心能力 out
- **三大测试承诺（宪法级）**：Recall_robust ≥ 90% / Acc_supersede ≥ 95% / E_align ≥ 60× / E_step ≥ 80%
- **角色**：三人协作（R1/R2/R3）为预留结构，当前实际为 单一贡献者 + Claude 副驾（Day 8 升级为双贡献者 + Claude）
- **Schema D1–D5**：单亲（parent_id+evolution_type）/ ROOT 入 enum / consensus_sources jsonb / pgvector v1 / W2 应用层 + 巡检
- **存储底座**：v1 = PG 单库（pgvector + 自引用）；v2 切 Qdrant / Neo4j 的触发条件入宪法 §3.3
- **DB 层强制**：W13（trace_log.trace_id PK NOT NULL）、W14（card_quota.count CHECK ≤ max_daily）
- **五维公式开放点 1 = (α)**：02-DESIGN 同步加 f_user_validation 因子（5 因子方案）
- **embedding 维度开放点 2**：确认采用 Doubao Embedding v1 = 1024 维
- **工作记录纪律**：CLAUDE.md §2.8 新增；PROGRESS.md 是单一权威记录源

### 遗留 / 当时未做

- 04-ENGUIDE / 05 / 06 待建（04 当日下午建立；06 在 Day 8 整合 NPU-src 时建立；05 仍延后）
- 代码骨架尚未启动（pyproject.toml / memory_engine/ 全空 → 见 Day 8 T-001）
- `validate_consistency.py` 尚未实现（→ T-003）

### LLM 调用

本日累计 0 次生产 LLM 调用（全部为文档创作 + 仓库探索）。
