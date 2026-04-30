# 工作记录 (PROGRESS.md)

> 项目过程证据；**按日倒序追加**。
> 格式与纪律见 [CLAUDE.md §2.8](./CLAUDE.md)。
> Day 1 = 2026-04-22（飞书 AI 校园挑战赛开赛日）；Day 23 = 2026-05-14（决赛日）。

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
