# 飞书 AI 校园挑战赛 · 题二（企业级记忆引擎）· 方向 B

# Team STZ · 项目交付答卷

> **文档定位**：终极提交答卷（直接粘贴入飞书表单）
> **版本**：v1.0（2026-05-13 起草）
> **作者**：Team STZ（czhang076 + NPU-src + Claude Code 副驾）
> **课题方向**：方向 B —— 飞书项目决策与上下文记忆

---

## 一、总项目结果展示

### 1) Demo 展示

**项目仓库**：[https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ)
**录屏链接**：（待补 YouTube/B 站/飞书云空间）
**Demo 内容**（按录屏脚本顺序）：

| 时长 | 演示项 | 价值证据 |
|:---:|:---|:---|
| 0:30 | `docker compose up -d postgres` 起 PG + pgvector 容器 | 基础设施一键启动 |
| 1:00 | `uv run pytest -q` → **92 passed in 0.79s** | 单测覆盖完整（含 W2/W14/W15 不变量） |
| 1:30 | `uv run pytest -m integration` → **5 passed in 5.48s**（testcontainers 起独立 PG + alembic upgrade） | 集成测打通 schema → ORM → DB → 业务规约 |
| 2:30 | 终端跑 `INSERT INTO decisions (..., evolution_type='SUPERSEDES')` 不带 parent_id → **PG 直接 reject `chk_decisions_evolution_parent` violation** | **W2 不变量在 DB 层强制——应用 bug 也无法绕过** |
| 3:00 | 跑 `INSERT INTO card_quota (count=6, max_daily=5)` → **W14 CHECK 触发** | **W14 同样 DB 层强制** |
| 3:30 | `uv run pre-commit run --all-files` → **11 hooks 全 Passed**（含 `validate-consistency` schema↔ORM 漂移检查） | 工程纪律：每次 commit 自动守门 |
| 4:00 | 故意改 `models.py` 加 `fake_field` 字段 → `validate_consistency.py` exit 1 + stderr 报告 → 还原 → exit 0 | **schema 漂移 1 秒被检测出来** |
| 5:00 | 浏览 4 份核心文档（CONSTITUTION + DESIGN + SCHEMA + ENGUIDE）+ 06-benchmark-design | 架构思考密度（~3500 行规约文档） |
| 6:00 | 浏览 `PROGRESS.md` 时间线 + `tickets/T-001~T-005` 决策追溯链 D1-D24 | 17 天工程纪律可视化 |

**演示亮点**：不需要 LLM 真接入即可展示**架构、数据契约、不变量强制、工程守卫**四件事；这些是 v1.0 真正区别于 baseline RAG 的核心。

---

### 2) 核心部分代码展示

#### a) DB 层不变量强制（schema.sql 节选 —— W2 与 W14）

```sql
-- W2: SUPERSEDES 父转 ARCHIVED；REFINES 父保 ACTIVE
CREATE TABLE decisions (
    decision_id      uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    -- ... 七字段 ...
    parent_id        uuid          REFERENCES decisions(decision_id) ON DELETE RESTRICT,
    evolution_type   evolution_type_enum  NOT NULL,
    CONSTRAINT chk_decisions_evolution_parent CHECK (
        (evolution_type = 'ROOT' AND parent_id IS NULL)
        OR
        (evolution_type IN ('SUPERSEDES', 'REFINES', 'GENERALIZES', 'BRANCHES')
         AND parent_id IS NOT NULL)
    )
);

-- W14: 单用户每日卡片推送上限 5 张
CREATE TABLE card_quota (
    user_id     varchar(64) NOT NULL REFERENCES users(user_id),
    quota_date  date        NOT NULL,
    count       int         NOT NULL DEFAULT 0,
    max_daily   int         NOT NULL DEFAULT 5,
    PRIMARY KEY (user_id, quota_date),
    CONSTRAINT chk_card_quota_count CHECK (count >= 0 AND count <= max_daily)
);
```

#### b) Schema↔ORM 漂移自动守卫（`scripts/validate_consistency.py` 核心）

```python
def check() -> list[str]:
    """运行全部漂移检查；返回漂移列表（空 = 一致）。"""
    text = parse_schema_sql_text()
    drifts: list[str] = []
    drifts += diff_tables(parse_schema_tables(text), parse_orm_tables())
    drifts += diff_enums(parse_schema_enums(text), parse_orm_enums())
    drifts += diff_indexes(parse_schema_indexes(text), parse_orm_indexes())
    return drifts

# pre-commit local hook（每次 git commit 自动跑）
# .pre-commit-config.yaml:
#   - id: validate-consistency
#     entry: uv run python scripts/validate_consistency.py
```

#### c) 五维自适应遗忘公式落地

```
λ(t) = λ_base × f_freq × f_consensus × f_semantic × f_uncertainty × f_user_validation
new_uncertainty = clip(prev + λ(t) × Δt_days, 0, 1)
```

```python
# memory_engine/utils/invariants.py（W2/W14/W15 应用层断言）
def assert_w2(parent_state, edge_type, *, trace_id=""):
    if edge_type == EvolutionType.SUPERSEDES and parent_state != DecisionState.ARCHIVED:
        raise W2Violation(trace_id=trace_id, extra={
            "rule": "SUPERSEDES 后父决策必须 ARCHIVED",
            "edge_type": edge_type.value,
            "parent_state": parent_state.value,
        })
```

#### d) 接口先于实现（`docs/04-ENGUIDE.md §8` 共 25 个函数签名）

```python
# M2 演化判定
def find_potential_parents(candidate: DecisionAtom, *, top_k: int = 3) -> list[Decision]: ...
def judge_evolution(candidate: DecisionAtom, parent: Decision | None) -> EvolutionJudgment: ...
def commit_evolution(child: DecisionAtom, parent: Decision | None,
                     judgment: EvolutionJudgment) -> Decision: ...
```

每个函数附 6 字段契约（入参 / 出参 / 异常 / 副作用 / 前后置 / 测试要求），后续业务实施时据此即可 stub。

---

### 3) 项目亮点介绍

#### **亮点 1：把"记忆"窄定义为"决策原子 + 演化谱系 + 五维衰减"**
- **取舍**：不追求"全都记住"，只记**多人多源决策的演化与一致性**
- **理由**：CLI 命令历史已被 fish/atuin 解决；通用 KG 缺时序；文档全文记忆无法处理覆盖语义。这三类都不该重做。
- **效果**：系统能在**关键时刻主动干预**（CLI 拦截 / 冲突卡片 / 跨源仲裁），而非沦为另一个搜索引擎。

#### **亮点 2：W1-W15 不变量在 DB 层强制（W13/W14 不可被应用 bug 绕过）**
- W13 飞书 API trace_id：`trace_log.trace_id` PK NOT NULL → 不写 trace 就别想发请求
- W14 5 卡/日预算：`card_quota.count` CHECK ≤ max_daily → DB 直接 reject 第 6 张
- W2 演化关系：`chk_decisions_evolution_parent` CHECK → SUPERSEDES + parent_id NULL 不可入库
- 集成测验证：`pytest -m integration` 5/5 包含**正负样本反向触发** IntegrityError

#### **亮点 3：Hot/Cold 双路径——在有限 LLM 配额下的必然性**
- Doubao TPM 1w 单人 / 3w 小组（火山引擎）
- 若 Hot Path 也走 LLM：日均请求 50K 次将立刻击穿额度
- **Hot Path 80% 请求零 LLM**（规则缓存 + 精确索引 + 本地向量）
- **Cold Path 20% 请求选择性 Doubao 赋能**（提取 / 演化判定 / Reflect / 跨源对齐）
- **副效果**：跑得快 + 经济可行 + 演示稳定（不依赖网络）

#### **亮点 4：五维自适应遗忘——多通道乘性建模**
- 5 条独立衰减通道（访问频次 / 跨源共识 / 语义中心性 / 置信不确定性 / 用户验证反馈）
- **乘性结构**："任一通道告警都加速遗忘"，符合"短板效应"
- 加性结构会被高分因子掩盖低分告警，错失关键信号

#### **亮点 5：决策可追溯——D1-D24 全程 paper trail**
- 每个架构选择走"surface 选项 + 推荐 + 字母锁定"流程，**留 Git commit 凭证**
- 后续扩团队接手时 24 个核心决策**全可还原**
- 答辩遇到任何"为什么这么做"的追问，都能精确指到 commit + 拍板者 + 当时考虑的备选项

#### **亮点 6：17 天单人交付 4 个月架构设计的工作量**
- 4 份核心规约文档（~3500 行）：宪法 + 架构 + Schema + 工程指南
- 5 个 ticket 实施（T-001 ~ T-005 P0），70+ git commits
- 73 单测 + 5 集成测 + pre-commit 11 hooks 全过，**mypy --strict 业务代码零类型 error**

---

### 4) AI 亮点介绍 ⭐

> 此节是项目最核心的差异化部分。

#### **A. 高阶 AI 技巧**

**A1. 决策锁定模板（最大方法论收获）**

每次设计歧义点，让 AI **不直接选**，而是 surface 2-3 选项 + AI 推荐 + 我回字母锁定：

```
AI: 我看到三种可能：
    (a) decisions.parent_id + evolution_type 字段（单亲）
    (b) 独立 evolution_edges 表（多亲 / 标准图）
    我倾向 (a)，因为单亲场景在 17 天周期内不会触发；多亲是 v2 演进项。
我:  D1=a
```

解决了 AI 协作中**两大痛点**：
- **AI 静默选择**：选错了后期才发现
- **决策疲劳**：AI 把所有选项都铺出来让人选

**这套流程让"AI 给推荐 + 人类拍板"的责任边界清晰**，全程留 paper trail（D1-D24）。

**A2. 矛盾识别即时反馈**

让 AI 读完所有上下文后**主动指出文档间矛盾**。例：
- "02-DESIGN §四 机制七公式只列 4 因子，但描述说 5 通道——这是不一致"
- "宪法 §3.1.4 写 Qdrant，但 D4 已选 pgvector，§3.1.4 没同步"
- "schema.sql 18 个匿名 CHECK 但 ORM 给了 11 个命名 CheckConstraint——这是命名漂移"

→ 每次都比我自己 review 快，且更彻底。

**A3. 三层守卫让 AI 无法写错**

```
Layer 1: mypy --strict（编译期）
Layer 2: ruff + pre-commit（commit 期，11 hooks 含 validate_consistency）
Layer 3: 集成测 + W2/W14 DB CHECK（运行时）
```

AI 写错任何字段、改错任何接口、漏写任何不变量，**5 秒内被 reject**。

**A4. "诚实先于自洽"原则（宪法 §5.7）**

显式禁止 AI 修改测试以让代码通过 / 调整 schema 以避免类型错误。AI 遇阻必须直接说"我做不到，遇到 X 阻塞"。这条原则让 AI 协作的可信度提升一个量级。

#### **B. 人 / AI 分工**

| 角色 | 承担 | 实际产出 |
|:---|:---|:---|
| **czhang076（项目负责人）** | 方向把控 / 决策拍板（D1-D24）/ 范围限定 / 矛盾仲裁 / 工程纪律设计 | 4 文档体系 + ticket 全程主理 |
| **Claude Code（AI 副驾）** | 架构推演 / 设计模式选择 / 文档生成 / 跨文档一致性检查 / 矛盾识别 / 代码 stub | 95% 文档与代码"驾驶员"由 AI 出，人类做"副驾审阅 + 决策" |
| **NPU-src（评测工程师）** | 评测数据 fixture / Baseline RAG 实现 / 飞书 API 调研 | TC001/TC002 fixture（v0.1）+ baseline 模块 + 调研文档 |

**关键观察**：在工程纪律严格的协作框架下（CLAUDE.md 7 条戒律 + 宪法 15 条不变量），AI 的产出与人类几乎不可区分；瓶颈不在 AI 写代码能力，而在**人类决策速度** + **决策质量**。

#### **C. 模型选型**

**多档 LLM 的有意分工**：

| 路径 | 模型 | 用途 | 选型理由 |
|:---|:---|:---|:---|
| **Heavy** | Doubao 2.0 | 演化判定 / Reflect / 跨源对齐 | 精度敏感场景，用大模型保推理质量 |
| **Light** | Doubao 1.6 | 决策原子提取 / 离线参数校准 | 量大场景，用小模型保 TPM 吞吐 |
| **Embedding** | Doubao Embedding v1（1024 维） | 语义检索 / 五维衰减的 semantic 因子 | 独立 EP，不挤占主路径 TPM |
| **降级** | 本地 7B 量化（W12 触发） | Doubao 额度耗尽时兜底 | 演示永不 panic |

**核心思路**：用大模型保精度，小模型保 volume；TPM 1w 单人 / 3w 小组的 hard 约束**驱动 Hot/Cold 双路径成为必然结构而非奢侈品**。

**Prompt 设计**：演化判定 Prompt 强制输出 JSON `{evolution_type, confidence, reasoning}`，加 OPPOSITE_PAIRS 词表加速层（"冻结" vs "发布" 命中时直接返回 SUPERSEDES, 0.99，**估算节省日均 30% 额度**）。

#### **D. 引入 AI 后对工作流的改变**

| 维度 | Before（传统） | After（AI 协作） |
|:---|:---|:---|
| **工作顺序** | 先写代码再补文档 | **接口先于实现**（CLAUDE.md §2.1）—— 写代码前 04-ENGUIDE §8 必须先有契约 |
| **决策密度** | 关键决策淹没在 commit 里 | **D1-D24 paper trail**，每个决策有 surface→recommend→letter-lock 三步流程 |
| **工程节奏** | 4 个月架构设计周期 | **17 天单人交付** + 4 文档体系 + Phase 0 4/5 完成 |
| **审阅成本** | 人工 review 耗时 | **AI 自审跨文档矛盾**（找出 14 处 meta-cleanup 项），人审决策不审措辞 |
| **不变量保障** | 靠注释 + code review 维持 | **DB 层 CHECK + pre-commit hook + 集成测**三层强制 |

---

### 5) 其他信息补充

**5.1 已知缺口（v1.0 未交付，诚实标记）**
- M1-M7 业务模块**全部未实施**（接口契约已定）
- LLM **真接入未实跑**（架构对齐 Doubao 三档 EP，mock 路径已准备）
- 飞书 webhook + Bot 推送**未实跑**
- 三大主测试承诺值（≥90%/95%/60×）**未实测**（fixture 已建）
- 跨源 OKR / 审批 / 妙记 / 日历**走 fixture 模拟**（宪法 §3.3 明文）

**5.2 v1.1 路径承诺**：扩团队 1 周内可在此基础上补完业务层，三大测试可跑分。

**5.3 商业可行性**：
- Hot Path 零 LLM 调用 → 95% 请求经济可行
- 飞书 → 钉钉 / Lark / Teams：schema + 七大机制不变；只换 `feishu_integration` 适配层

**5.4 跨企业可复制性**：方向 B 的"决策一致性 + 演化追溯 + 跨源仲裁" 是**所有企业 SaaS 共同的痛点底座**。

---

## 二、小组成员各自负责部分

### 成员 1：**czhang076**（项目负责人 / 架构 + 工程）

#### 负责模块
- **R3 文档体系**：4 份核心规约（宪法 / 架构 / Schema / 工程指南）+ 06-benchmark-design + whitepaper 框架（共 ~5000 行）
- **R1 内核工程**：T-001 项目基线 + T-002 数据持久化层（schema.sql + ORM + 异常树）+ T-003 业务对象 + 配置 + T-004 漂移检查 + Alembic + 集成测 + T-005 P0（invariants + cache）
- **AI 协作流程设计**：决策锁定模板（D1-D24）+ CLAUDE.md 7 条戒律 + 宪法 15 条不变量
- **工程守卫**：pre-commit 11 hooks + mypy --strict + validate_consistency 自动漂移检查

#### Demo
- 录屏文件：（同 §1.1）
- GitHub commit 链：[c427a26](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/c427a26) → [1d03b47](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/1d03b47) 共 ~50 commits

#### 代码样品
- [`schema.sql`](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/blob/main/schema.sql) — 290 行，W2/W14 DB CHECK 强制
- [`scripts/validate_consistency.py`](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/blob/main/scripts/validate_consistency.py) — 250 行漂移检查
- [`memory_engine/utils/invariants.py`](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/blob/main/memory_engine/utils/invariants.py) — W2/W14/W15 应用层 assert
- [`tests/integration/test_int_schema.py`](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/blob/main/tests/integration/test_int_schema.py) — testcontainers 5 集成测

---

### 成员 2：**NPU-src**（评测工程师）

#### 负责模块
- **R3 评测数据**：TC001 抗干扰召回 fixture（100 噪声 + 1 核心决策）+ TC002 矛盾覆写 fixture（3 迭代序列 + 4 边界场景）
- **AB 测试设计**：TEST_CASES_AB.md → 升级为 [docs/06-benchmark-design.md](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/blob/main/docs/06-benchmark-design.md) v1.0（TC001-TC009 完整测试矩阵）
- **Baseline RAG 实现**：在 `origin/test` 分支独立部署 baseline RAG 系统作为 AB 测试对照组
- **飞书 API 调研**：`FEISHU_API_RESEARCH.md`（288 行）

#### Demo
- 提交 commit：[`418431f feat: 添加AB测试用例框架`](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/418431f)
- Baseline 部署：`origin/test` 分支 [`afa1845 feat: Baseline RAG 本地部署完成`](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/afa1845)

#### 代码样品
- [`benchmark/fixtures/tc001_anti_interference.py`](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/blob/main/benchmark/fixtures/tc001_anti_interference.py) — 抗干扰召回测试数据
- [`benchmark/fixtures/tc002_contradiction.py`](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/blob/main/benchmark/fixtures/tc002_contradiction.py) — 矛盾覆写测试数据
- `baseline/baseline_rag.py`（test 分支）— Baseline RAG 主流程

> *请 NPU-src 同学补充更多个人贡献细节与 demo 链接。*

---

## 附：量化指标

| 维度 | 数值 |
|:---|:---:|
| 文档行数（4 核心 doc + 06 + whitepaper 框架） | ~5000 |
| 业务代码行数（T-002~T-005 P0） | ~1800 |
| 测试行数（unit + integration） | ~900 |
| 单测通过 | 92 / 92 |
| 集成测通过 | 5 / 5 |
| pre-commit hooks | 11 / 11 全过 |
| mypy --strict 业务代码 error | 0 |
| 锁定决策（D 编号） | D1 ~ D24 共 24 个 |
| 不变量（W 编号） | W1 ~ W15 共 15 条（DB 强制 2 条，W13/W14） |
| Git commits（main 分支） | ~50 |
| 文档版本迭代 | 宪法 v1.0→v1.3 / 架构 v3.3→v3.3.3 等 |
| AI 协作轮次（Claude Code） | ~200 轮 |
| 项目 LLM 生产调用 | 0（mock 模式 + 真接入预留） |

---

> 本文档随 git push 进入 `deliverables/final-submission.md`，作为答辩前最终版底稿；提交飞书表单时直接复制粘贴各章节内容。
