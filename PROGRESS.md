# 工作记录 (PROGRESS.md)

> 项目过程证据；按日倒序追加。
> 格式与纪律见 [CLAUDE.md §2.8](./CLAUDE.md)。
> Day 1 = 2026-04-22（飞书 AI 校园挑战赛开赛日）；Day 23 = 2026-05-14（决赛日）。

---

## 2026-04-29 · Day 8 · NPU-src 整合 + 协作纪律 v1.3

### 改动（czhang076 + Claude）
- 整合 NPU-src 在 commit `418431f` 推送的 AB 测试框架（fast-forward 拉取）
- **fixture 路径重组**：`tests/fixtures/*` → `benchmark/fixtures/*`（04-ENGUIDE §1 对齐）；`tests/validate_fixtures.py` → `benchmark/validate_fixtures.py`（修复 import 路径 + sys.path 兜底，支持脚本与模块两种调用）
- 新建 `benchmark/__init__.py` + `benchmark/fixtures/__init__.py`
- **删除被 v3.3 取代的旧文档**：`ARCHITECTURE.md` / `METRICS.md` / `TEST_CASES_AB.md`（其内容已被 docs/02-DESIGN 和新建的 docs/06-benchmark-design 取代）
- **新建 [docs/06-benchmark-design.md](./docs/06-benchmark-design.md) v1.0**：基于 NPU-src TEST_CASES_AB 重组为标准化文档；TC001-TC009 + 评分规则 + fixture 契约；与宪法 §8 承诺值显式对照；与 04-ENGUIDE §8 接口一一映射
- **宪法 [v1.2 → v1.3](./docs/01-CONSTITUTION.md)**：§10.2 双贡献者结构 + §10.3 多人协作纪律重写 + §11 状态行 + 附录 B v1.3 行
- **CLAUDE.md [v1.2 → v1.3](./CLAUDE.md)**：§3.1 双贡献者 + 多人协作纪律落地

### NPU-src 贡献（独立 commit 418431f）
- TC001 / TC002 fixture 数据（已迁到 `benchmark/fixtures/`，结构无变化）
- TC001-TC009 测试用例设计（已重组为 docs/06-benchmark-design.md）
- 旧 ARCHITECTURE.md / METRICS.md（已识别为 v3.3 取代品，本轮删除）

### 决策
- **整合方案 (A)**：保留 NPU-src 有价值产出，删除被 v3.3 淘汰的旧文档，迁移 fixture 路径
- **NPU-src 子领地 = `benchmark/fixtures/`**（宪法 §10.2）
- **多人协作纪律**：每次 push 前 `git pull origin main`；删文件前 grep 引用 + 跟另一贡献者确认；新路径必更 04-ENGUIDE §1
- **T-001 ticket 文档已就绪**（昨日草稿，今日确认），等本 commit push 后实施 21 文件实际生成

### 遗留
- **T-001 实施待启动**：pyproject.toml + .env.example + docker-compose.yml + 包结构 + 各 __init__.py 约 21 文件（暂停在 commit `e87504c` 后）
- TC003-TC009 fixture 待建（T-005 阶段实施）
- TC001 fixture v0.1 噪声 100 条 → 赛事级 1000 条目标，T-005 扩展
- 与 NPU-src 实际人对人沟通：发个 ping 让他读 04-ENGUIDE §1 + 宪法 §10.3，避免下次再复活旧文档（这是 czhang076 的人工动作，不属于 Claude 任务）

### LLM 调用
本会话 0 次生产调用（文件操作 + 文档生成）

### 当日 LLM 调用累计
0 次

---

## 2026-04-27 · Day 6 · 文档体系底座

### 改动
- [CLAUDE.md](./CLAUDE.md) v1.0 → v1.2：对齐 DESIGN.md v3.3（5 处：版本头 / §2.3 范围 / §2.6 依赖流程 / §3.1 角色 / §7 状态）；新增 §2.8 工作记录习惯
- 根目录 `DESIGN.md` → [docs/02-DESIGN.md](./docs/02-DESIGN.md)；§四 机制七 五维公式补 `× f_user_validation` 因子（与 03-SCHEMA 对齐）；v3.1/v3.2 残留措辞改为 v3.3
- 删除 `ARCHITECTURE.md`（旧试行版） + `METRICS.md`（旧指标体系）
- 新建 [docs/01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) v1.0 → v1.1（412 行；11 主节 + 2 附录；§3.1.4 / §3.3 范围级修订纳入 D1/D4 决策）
- 新建 [docs/03-SCHEMA.md](./docs/03-SCHEMA.md) v1.0（702 行；8 主表 + 6 enum + 状态机 + W1–W15 落点映射）
- 新建 [PROGRESS.md](./PROGRESS.md)（本文件）+ [.gitignore](./.gitignore)

### 决策
- **范围**：v3.3 七大机制 + 三大主测试全部 in scope；方向 A / C 核心能力 out
- **三大测试承诺（宪法级）**：Recall_robust ≥ 90% / Acc_supersede ≥ 95% / E_align ≥ 60× / E_step ≥ 80%
- **角色**：三人协作（R1/R2/R3）为预留结构，当前实际为 单一贡献者 + Claude 副驾
- **Schema D1–D5**：
  - D1 = (a) `decisions.parent_id` + `evolution_type` 字段（单亲模型）
  - D2 = (a) ROOT 是 enum 值之一（5 值）
  - D3 = (a) `consensus_sources` jsonb（不开独立 sources 表）
  - D4 = (b) v1 用 pgvector（v2 触发条件入宪法 §3.3）
  - D5 = (b)+(c) W2 由应用层 + 巡检任务双保险，不用 PG 触发器
- **存储底座**：v1 = PostgreSQL 单库（pgvector + decisions 自引用）；v2 切 Qdrant / Neo4j 的触发条件已写入宪法 §3.3
- **DB 层强制**：W13（`trace_log.trace_id` PK NOT NULL）、W14（`card_quota.count` CHECK ≤ max_daily）
- **五维公式开放点 1 = (α)**：02-DESIGN 同步加 `f_user_validation` 因子（5 因子方案）
- **embedding 维度开放点 2**：确认采用 Doubao Embedding v1 = 1024 维
- **工作记录纪律**：CLAUDE.md §2.8 新增；PROGRESS.md 是单一权威记录源

### 遗留
- 04-ENGUIDE / 05-edge-discipline / 06-benchmark-design 未建；接口契约未定 → 任何代码 ticket 都不能开工（CLAUDE.md §2.1 接口先于实现）
- 代码骨架：`memory_engine/` / `feishu_integration/` / `tests/` / `schema.sql` / `models.py` 全部尚未存在
- `validate_consistency.py` 尚未实现（03-SCHEMA 附录 A 已给出规约）

### 后续 — 04-ENGUIDE 创建（同日下午）

**改动**：
- 新建 [docs/04-ENGUIDE.md](./docs/04-ENGUIDE.md) v1.0（~720 行；§8 接口契约总表覆盖 M1–M7 + 共享工具 + CLI 共 ~25 个函数签名）
- [docs/01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) §11 状态行更新（下游文档列表加入 04-ENGUIDE）

**决策**：
- 代码风格：v1 全同步（FastAPI / SQLAlchemy 2.0 / httpx 同步）；async 留 v2
- 数据三层：API DTO ↔ pydantic v2 业务对象 ↔ SQLAlchemy ORM；ORM 不出 `memory_engine` 包
- 模块依赖红线：M1–M7 不直接相互调用，必须经 `cold_path` 编排；`utils/` 不调任何 M1–M7 业务模块
- v1 同步函数调用；事件总线（Redis Streams / PG LISTEN）推迟到 v2
- LLM 网关与飞书网关为强制层；W13 由 `feishu_client` + DB NOT NULL 双层保证
- 单测必须 mock LLM / 飞书 API；唯一例外是 `@pytest.mark.live` 端到端基准测试

**遗留**：
- 05-edge-discipline / 06-benchmark-design 待建
- 代码骨架仍未建立（pyproject.toml / requirements.txt / memory_engine/ 全空）；**接口契约已就位 → 首个代码 ticket 可开工**

**LLM 调用**：本轮 0 次

### 后续 — 资源配置刷新 + Phase 0 计划锁定（同日傍晚）

**改动**：
- [docs/01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) v1.1 → v1.2：§3.2 微调禁令理由更新；§3.3 加任务调度切换 Conditional Scope 行；§4.1 资源表全面刷新（Doubao 2.0/1.6 + Embedding v1，TPM 1w 单人 / 3w 小组）；§11 状态行；附录 B v1.2 行
- [docs/02-DESIGN.md](./docs/02-DESIGN.md)：replace_all `Seed-2.0` → `Doubao`（17 处）；header 加 LLM 命名口径段；§二 LLM 配额段 TPM-aware；§四 机制三 budget header TPM-aware；§十一 LLM 服务行 + 任务调度行（APScheduler v1 / Celery v2）
- [docs/04-ENGUIDE.md](./docs/04-ENGUIDE.md) §4.4：LLM 调用预算表加"模型"列（Heavy=2.0 / Light=1.6 / Embedding 独立）；加 TPM 网关强制行为说明

**决策**：
- **D6 = (b)**：v1 任务调度 = APScheduler（同进程内存）；v2 切 Celery + Redis 触发条件已写入宪法 §3.3
- **D7 = (b)**：Python 3.12 锁定（T-001 pyproject.toml 直接定）
- **D8 = (a)**：T-001 提供 `docker-compose.yml`（PG 16 + pgvector）
- **D9 = (a)**：Phase 0 完成后，第一个业务 ticket = M1 + M2 + M5 端到端切片
- **隐含 D10**：Heavy 路径默认 Doubao 2.0，Light 路径默认 Doubao 1.6（推论自"用大模型保精度，小模型保 volume"），如不同意需 ticket 阶段调整
- **资源命名口径**："Seed-2.0" 全部改为 "Doubao"；具体分工以 04-ENGUIDE §4.4 为准
- **TPM 替代 calls/day**：约束底层是 TPM 1w 单人 / 3w 小组，calls/day 仅为派生参考

**遗留**：
- T-001 ~ T-005 计划已就位，**等用户 WSL 环境探索后启动**
- 05-edge-discipline / 06-benchmark-design 仍待建（不阻塞代码骨架）
- 火山引擎 EP 实际数值（DOUBAO_2_ENDPOINT_ID / DOUBAO_1_6_ENDPOINT_ID / DOUBAO_EMBED_ENDPOINT_ID）尚未认领，T-001 时填 .env.example 占位

**LLM 调用**：本轮 0 次

### 当日 LLM 调用累计
0 次生产调用（全部为文档创作 + 资源配置刷新）。

---

## 2026-04-29 · Day 8 · NPU-src 整合 + T-001 项目基线落地

### 早间 — NPU-src AB 测试框架整合（commit 418431f → a890dc0）

**背景**：NPU-src 在 commit `418431f` 推送了 AB 测试框架（TC001-TC009 + 数据 fixture），但同时复活了我们已删除的旧文档（ARCHITECTURE.md / METRICS.md），并把 fixture 放在了 `tests/fixtures/`（与 04-ENGUIDE §1 规约的 `benchmark/fixtures/` 不一致）。

**改动**（commit `a890dc0 feat: 整合 NPU-src AB 测试框架 + 协作纪律 v1.3`）：
- `git pull` 拉下 418431f
- 重新删除 `ARCHITECTURE.md` / `METRICS.md`（与 v3.3 设计冲突）
- `git mv tests/fixtures/* → benchmark/fixtures/`（保留 git history）
- `git mv tests/validate_fixtures.py → benchmark/validate_fixtures.py`（修 import 路径 + 加 sys.path 兜底）
- 新建 `benchmark/__init__.py` + `benchmark/fixtures/__init__.py`
- 把 `TEST_CASES_AB.md`（111 行）整合并升级为 [docs/06-benchmark-design.md](./docs/06-benchmark-design.md) v1.0（408 行；TC001-TC009 + 评分规则 + 与宪法承诺值 + 04-ENGUIDE §8 接口对应表）
- [docs/01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) v1.2 → v1.3：§10.2 加 NPU-src 为 active 贡献者，§10.3 由"单人纪律"重写为"多人协作纪律"（pull-before-push、删文件先确认、新路径必更 04-ENGUIDE §1）
- [CLAUDE.md](./CLAUDE.md) v1.2 → v1.3：§3.1 双贡献者 + 子领地划分

**决策**：
- 整合方案 = **(A) 全盘整合**：保留 NPU-src 有价值产出（TC001/TC002 fixture v0.1）；删除冗余旧文档
- NPU-src 加为 active 贡献者，子领地 = `benchmark/fixtures/`
- 06-benchmark-design v1.0 不重写 NPU-src 内容，而是包裹标准化 doc header + 加交叉引用

### 午间 — T-001 项目基线实施（WSL 内）

**改动顺序**（共 5 个 commit）：

1. `c427a26 feat(T-001): 项目基线 + 包结构（22 文件）` —— pyproject.toml、.python-version、.env.example、.gitattributes、.pre-commit-config.yaml、alembic.ini、docker-compose.yml、migrations/env.py、conftest.py、tests/conftest.py、~10 个 `__init__.py`、README.md（quick-start 段落）
2. `a69dbb1 fix(T-001): mypy exclude 加 benchmark/fixtures/ 与 validate_fixtures.py` —— 数据文件不挤 mypy --strict
3. `fbdfac7 fix(T-001): validate_fixtures.py 加最小类型注解通过 mypy strict` —— `types: dict[str, int] = {}`
4. `1f6ac1a fix(T-001): pre-commit mypy exclude 加 validate_fixtures.py` —— exclude 模式补全
5. `6f957ae chore(T-001): pre-commit auto-fixes + uv.lock` —— ruff 自动重格式化（imports 拆分、`# type: ignore[operator]`）+ 锁文件

**T-001 DoD 全部 ✓**：
- `uv sync` 装齐 71 包（生产 12 + 开发 9 + 传递依赖）
- `pre-commit run --all-files` 全过（ruff format / ruff check / mypy --strict / yaml / toml / merge / large-file / line-ending）
- `docker compose up -d postgres` → `feishu-memory-pg healthy` (端口 5432)
- pgvector **0.8.2** 已装（PG 16 + plpgsql 1.0 + vector 0.8.2）
- `uv run pytest -q` → `no tests ran in 0.01s`（exit 0 = 0 测试预期通过）
- `uv run python -m benchmark.validate_fixtures` → TC001 / TC002 数据正常加载

### 卡壳与破局

| 问题 | 破局 |
|:---|:---|
| **mypy --strict 把 NPU-src fixture 数据文件标红 7 处** | `[tool.mypy]` 加 exclude 列表 + pre-commit hook 同步 exclude；validate_fixtures.py 给 `types` 显式注解 |
| **pyproject.toml 的 `tool.uv.dev-dependencies` 在 uv 0.11 已废弃** | 改用 `[dependency-groups] dev = [...]`（PEP 735） |
| **bash heredoc + WSL 透传时 `[[ ... ]]` 模式匹配崩** | 简化为 `sleep + 直接验证`，避免在 wsl bash -lc '...' 内嵌套复杂 bash 控制流 |
| **WSL 端 git push 卡 credential prompt（PAT 未存）** | format-patch 绕道：WSL `git format-patch` → 落到 `/mnt/e/wsl-patches/` → Windows `git am` 应用 → Windows push（凭据已存） → WSL `git pull` 同步回拉 |
| **Git Bash 的 MSYS_PATH_CONV 把 `/home/...` 改写成 `D:/Git/home/...`** | 全程 `MSYS_NO_PATHCONV=1 wsl -d Ubuntu -u zero -- bash -lc '...'` |

### 决策（本日新锁定）

- **mypy --strict 范围**：业务代码（memory_engine / feishu_integration / cli / scripts / migrations）严管；benchmark/fixtures + validate_fixtures.py exclude（数据文件容许灵活）
- **uv 依赖组语法**：用 PEP 735 `[dependency-groups]` 而非旧的 `[tool.uv.dev-dependencies]`
- **WSL push 工作流**：当前阶段 WSL 端不存 PAT，用 format-patch 中转；T-002 前可改用 Git Credential Manager bridge 或写 `~/.git-credentials`

### 遗留 / 下一步

- **WSL git push 流程**：暂用 format-patch 中转。T-002 前可执行 `git config --global credential.helper '/mnt/c/Program\ Files/Git/mingw64/bin/git-credential-manager.exe'` 让 WSL 共享 Windows 凭据
- **pgvector Python binding**：容器侧已装 0.8.2，但 SQLAlchemy 侧 `pgvector` Python 包尚未冒烟测试 → T-002 ORM 实现时验证
- **下一个 ticket = T-002**：写 `memory_engine/{models.py, types.py, exceptions.py, config.py}` + `schema.sql` + `scripts/validate_consistency.py`（首个真业务代码 ticket）
- **NPU-src 协作沟通**：建议告知他读 [04-ENGUIDE §1](./docs/04-ENGUIDE.md) 路径规约 + [01-CONSTITUTION §10.3](./docs/01-CONSTITUTION.md) 协作纪律，避免下次推送再复活旧文档

### LLM 调用

本日累计 0 次生产调用（全部为文档 + 项目骨架 + 工具链整合）。Claude Code 协作约 ~15 轮，含 NPU-src 冲突分析、T-001 22 文件批量生成、5 次 pre-commit 修复迭代、format-patch 同步策略推导。

---
