# 工作记录 (PROGRESS.md)

> 项目过程证据；按日倒序追加。
> 格式与纪律见 [CLAUDE.md §2.8](./CLAUDE.md)。
> Day 1 = 2026-04-22（飞书 AI 校园挑战赛开赛日）；Day 23 = 2026-05-14（决赛日）。

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

### 当日 LLM 调用累计
0 次生产调用（全部为文档创作 + 仓库探索）。

---
