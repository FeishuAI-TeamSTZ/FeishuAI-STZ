# CLAUDE.md

> Project: OpenClaw FIE - 飞书企业级长程协作 Memory 系统
> Version: 1.3
> Last Updated: 2026-04-29
> Audience: Claude Code, Cursor, any AI coding agent in this repository

---

## 0. 必读优先级（Reading Order）

每次新会话开始时，按以下顺序加载上下文：

1. 本文件（CLAUDE.md）— 行为约束
2. `docs/01-CONSTITUTION.md` — 项目宪法
3. `docs/02-DESIGN.md` — 项目架构设计
4. `docs/03-SCHEMA.md` — 数据模型规约
5. `docs/04-ENGUIDE.md` — 主线工程实施纲要
6. `docs/06-benchmark-design.md` — 评测设计（TC001-TC009）
7. 当前 ticket（位于 `tickets/` 目录）

如果上下文中有任何缺失，**立刻列出**，不要假设。
**禁止**：跳过 1-6 直接进入 ticket。任何代码必须基于宪法和 Schema。

> 注：`docs/05-edge-discipline.md` 跨源接入边界文档**待建**（宪法 §3.3 跨源条件触发后才需要），当前可跳过加载，不算"缺失"。

---

## 1. 通用行为原则（Karpathy 4 + 项目补充）

### 1.1 不要默默假设（Don't assume silently）

如果不清楚需求，**停下来问**。
如果有多种解释，**列出 2-3 种让人选**，不要沉默选择一个。
如果发现宪法/Schema/ADR 和当前 ticket 之间有矛盾，**立刻指出**，不要试图自己调和。

具体应用：
- ❌ "我假设 evolution_type 默认是 ROOT"
- ✅ "Schema 没说 evolution_type 默认值。我看到三种可能：(a) 设置默认值 ROOT；(b) 必填；(c) Optional[None]。我倾向 (b)，因为符合 W2 演化关系不变量与 03-SCHEMA §2.2 CHECK 约束，是否同意？"

### 1.2 外科手术式改动（Surgical Changes）

只改 ticket 明确要求改的部分。**不要顺手"优化"其他代码**。

具体应用：
- ❌ 修一个 bug 时顺手重构 3 个不相关的文件
- ❌ 写新函数时顺手"清理"已有代码的命名
- ✅ 如果你认为某处代码该改但不在 ticket 范围内，**写到 PR 的"建议"区**，不要在本 PR 改

### 1.3 简洁优先（Simplicity First）

如果你写了 200 行而 50 行就够，**重写**。
不要为了"未来扩展性"引入抽象。
不要写 ticket 没要求的功能。

具体应用：
- ❌ "我提前实现了 v2.x 的 Playbook 兼容层"——出 scope，不该做
- ✅ 200 行做完，主动说"我可能还能压到 100 行，要不要再迭代一次"

### 1.4 目标驱动（Goal-Driven）

实现完后，**自己跑测试**，确认通过。
如果测试不通过，**先说明原因**，再决定是改实现还是改测试。
任何 ticket 的"完成"都必须有可验证的 DoD（Definition of Done），不要靠主观判断。

---

## 2. 项目特定戒律（Project Discipline）

### 2.1 接口先于实现（Interface First）

**任何模块开发前**：
1. 检查 `docs/04-engineering-guide.md §8 接口契约总表`
2. 如果接口未定义，停下来要求 R3 先补充契约
3. 不要自己发明接口

### 2.2 评测先于功能（Test First）

**任何能力的测试用例必须在功能实现前已存在**：
1. 写代码前，确认 `tests/fixtures/` 中有对应的 fixture
2. 写代码前，确认 `tests/test_*.py` 中有对应的测试函数（哪怕是 `pass`）
3. 实现完后，跑测试，必须通过

### 2.3 范围严格限定（Scope Discipline）

ticket 范围严格按 DESIGN.md v3.3 七大机制 + 三大主测试：
- ✅ 飞书全源接入（消息/OKR/审批/文档/妙记/日历）+ CLI 拦截端到端
- ✅ 演化判定（ROOT/SUPERSEDES/REFINES/GENERALIZES/BRANCHES）
- ✅ Hot/Cold 双路径 + 五维自适应遗忘
- ✅ 三大主测试（抗干扰/矛盾覆写/效能）+ S1–S6 支撑指标
- ⚠️ 任何 ticket 必须在描述中明确"属于哪个机制 + 覆盖哪个测试"
- ❌ 方向 A 核心能力（CLI 命令前缀补全 / 参数自动联想）
- ❌ 方向 C 核心能力（隐式偏好学习 / 自动化执行）
- ❌ Reflect 的"质量档案 → Prompt 自优化"完整闭环（保留单次 Reflect）
- ❌ 任何依赖梯度训练 / 微调的方案

如果 ticket 描述中出现 ❌ 项或边界模糊的内容，**指出歧义并停下**。

### 2.4 Schema 一致性（Schema Consistency）

`schema.sql` 和 `models.py` 必须一一对应。

**任何 Schema 改动**：
1. 先改 [`docs/03-SCHEMA.md`](./docs/03-SCHEMA.md)（数据契约源头）
2. 再改 `schema.sql`（T-002 创建后启用）
3. 再改 `memory_engine/models.py`（T-002 创建后启用）
4. 跑 `python scripts/validate_consistency.py`（T-003 实现后启用）
5. 在 PR 中说明"我改了 X 字段，原因 Y"

不允许只改一边。

### 2.5 LLM 调用透明（Transparent LLM Usage）

**任何使用 LLM 的代码**必须：
1. 通过 `utils.light_llm_extract()` 或 `utils.heavy_llm_extract()`，不要直接调 API
2. 在 PR 描述中说明"该 PR 在测试中触发了 N 次 LLM 调用"
3. 单元测试必须 mock LLM 调用（除非是集成测试）

**禁止**：在 main code path 中调用未经预算控制的 LLM。

### 2.6 不引入新依赖（No New Dependencies）

`pyproject.toml` 已锁定 21 包（生产 12 + 开发 9，PEP 621 `[project.optional-dependencies]`）+ `uv.lock` 锁版本，已经够用。

如果你认为需要新依赖：
1. 在 PR 描述中明文说明：依赖名 / 用途 / 替代方案 / 是否纯 dev 工具
2. 至少一名 active 贡献者（见宪法 §10.2）✅ 才能加入
3. 默认拒绝（除非真的必需）

### 2.7 诚实先于自洽（Honest over Coherent）

如果实现遇到问题：
- ❌ 不要"修改测试以让代码通过"
- ❌ 不要"调整 Schema 以避免类型错误"
- ✅ 直接说"我做不到，遇到了 X 阻塞"

如果发现 Schema/接口/宪法有错误：
- ✅ 在 PR 中明文指出
- ❌ 不要默默改它

### 2.8 工作记录持续化（PROGRESS.md）

每次会话结束 / 每个 PR 合并前，必须在仓库根目录的 `PROGRESS.md` 中追加一段工作记录。

**记录格式**：
- 顶部按日期倒序（最新在最上）
- 每天一个 `## YYYY-MM-DD · Day N · <主题>` 标题（Day N 从 2026-04-22 赛事开赛起算）
- 每个会话或 PR 作为子条目，包含：
  - **改动**：文件 + 一句话简述
  - **决策**：本次锁定的设计决定（如 D1=a / 范围级修订）
  - **遗留**：开放点、待确认假设、未跑测试
  - **LLM 调用次数**：含调试估算（宪法 §4.4 预算追踪）

**禁止**：
- 工作记录散落在 commit message / PR 描述而 `PROGRESS.md` 不更新
- 写"做了一些工作"之类的虚词
- 修改历史日期记录（订正错字除外）

**理由**：宪法 §10 当前角色为单人 + Claude，无 standup、无团队 wiki；`PROGRESS.md` 是赛后扩团队接手时唯一的过程证据，也是答辩复盘"我们怎么从零做出 v1.0"的素材源。

---

## 3. 协作纪律（Multi-Agent Coordination）

### 3.1 角色分工（双贡献者 + Claude 副驾，自 v1.3 起）

本项目设计为三角色协作，当前为 **双贡献者 + Claude 副驾**（详见 [宪法 §10.2](./docs/01-CONSTITUTION.md)）：

- **R1 内核工程师**：负责 `memory_engine/` 下的核心算法（暂未动工）
- **R2 接入工程师**：负责 `feishu_integration/` 和 `cli/`（暂未动工）
- **R3 评测+产品工程师**：拆为两个子领地
  - **czhang076 子领地**：宪法 / 架构 / Schema / 工程指南 / Ticket（`docs/`、`tickets/`）
  - **NPU-src 子领地**：评测数据 fixture（`benchmark/fixtures/`）

**多人协作纪律**：
- **每次 push 前先 `git pull origin main`** —— 基于过期 branch 工作是合并冲突与文档复活的主要根因（参考 NPU-src 在 418431f 误复活 ARCHITECTURE.md / METRICS.md 的教训）
- **删文件前先 grep 引用 + 跟另一贡献者确认** —— 不要默认"我看不见的就是不存在的"
- **目录归属以 [04-ENGUIDE §1](./docs/04-ENGUIDE.md) 为准**：docs/ / benchmark/fixtures/ / tests/ / scripts/ 各有领地
- **新增不在 04-ENGUIDE §1 路径里的文件** → PR 描述说明，必要时同步更 04-ENGUIDE §1
- 一次会话 / PR 尽量只覆盖一个子领地；Claude 跨子领地改动必须在响应中显式列出"改了哪些原属哪个领地的文件 + 理由"
- 任何文件首次创建时，在 PR 描述中说明（替代原"团队群通知"）

**扩团队时**：R1 / R2 角色直接分配新成员，子领地划分模板见 §10.2。

### 3.2 ticket 完成定义（DoD）

任何 ticket 完成必须满足：
- [ ] 实现了 ticket 描述的功能（且仅实现该功能）
- [ ] 单测通过（含相关 fixture）
- [ ] docstring 保留并补充实际行为
- [ ] PR 描述说明 LLM 调用次数
- [ ] PR 描述列出"未做但建议未来做"的事项
- [ ] 至少 1 人 review

未达 DoD 的 PR **禁止合并**。

---

## 4. 紧急情况处理（Escalation）

如果遇到以下情况，**立刻停止编码，等待人工决策**：

1. ticket 与宪法 / 02-DESIGN / 03-SCHEMA / 04-ENGUIDE 冲突
2. ticket 描述模糊到无法开始
3. 需要新依赖
4. 需要修改 schema.sql
5. 需要跨人协作（修改不属于自己的目录）
6. 评测无法通过且原因不明
7. LLM 调用次数超过 ticket 预算

**不要试图"自行处理"**。停下来，写一个 issue，等人工决策。

---

## 5. 上下文获取规则（Context Loading）

启动时务必加载：
/docs/01-CONSTITUTION.md          # 项目宪法
/docs/02-DESIGN.md                # 项目架构设计
/docs/03-SCHEMA.md                # 数据模型规约
/docs/04-ENGUIDE.md               # 主线工程实施纲要
/docs/06-benchmark-design.md      # 评测设计（TC001-TC009）
当前 ticket（位于 tickets/ 目录）
如有缺失，先列出，不要假定。

注：/docs/05-edge-discipline.md 待建（跨源 OKR/审批/妙记/日历真接入触发后才写，宪法 §3.3）；当前可跳过，不算缺失。

---

## 6. 性能与成本约束

每个 ticket 默认预算（在 ticket 中可被覆盖）：
- LLM 调用：≤ 50 次（含调试）
- 代码行数：≤ 500 行
- 文件改动数：≤ 5 个文件
- 运行测试时间：≤ 60 秒

超过任一项，**停下来汇报**，等待批准。

---

## 7. 当前阶段状态（Auto-Updated）

当前周期：Phase 2 / Day 8（T-001 项目基线落地，可启动业务代码 ticket）
七大机制实现进度：M1–M7 = 未启动；接口契约就位（04-ENGUIDE §8）
三大主测试 fixture：TC001 / TC002 v0.1 已建（NPU-src 贡献，benchmark/fixtures/）；TC003-TC009 待建
评测达标情况：Recall_robust / Acc_supersede / E_align / E_step / S1–S6 = 未跑分（基础设施就位，等业务代码）
代码骨架：✅ 22 文件 + 71 包 + Docker PG+pgvector 0.8.2 + pre-commit 全过 + pytest 通；下一个 ticket = T-002（models / types / exceptions / config / schema.sql）
最近修订：2026-04-29 v1.3（双贡献者协作纪律 + T-001 完成）

> 此节每天更新一次。Agent 启动时确认此节是最新状态。
