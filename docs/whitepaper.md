# 飞书决策一致性引擎 · 白皮书

> **副标题**：企业级长程记忆的窄定义与工程化路径——以飞书生态决策一致性中枢为切入
> **作者**：Team STZ（czhang076 / NPU-src + Claude Code 副驾）
> **应用场景**：企业级多人多源决策一致性中枢
> **版本**：v0.1（框架草稿）
> **目标读者**：技术决策者 / 产品经理 / 后续团队接手者
> **目标字数**：~5000 字 + 附录
> **文档地位**：项目对外公开的总览交付物；内部规约见 [01-CONSTITUTION](./01-CONSTITUTION.md) ~ [06-benchmark-design](./06-benchmark-design.md)

---

## 0. 摘要（~200 字）

> **填肉指引**：开门见山三段——(1) 问题；(2) 我们的窄定义；(3) 一句话价值。

- 问题：大模型"每次从零开始"在企业**多人多源决策**场景下的代价（决策被覆盖无人察觉 / 跨源不一致 / CLI 拦截缺位）
- 我们的回答：把企业级记忆**窄定义**为"带演化谱系 + 跨源共识度 + 五维时效衰减的**决策原子**集合"
- 一句话价值：飞书全源（消息 / OKR / 审批 / 文档 / 妙记 / 日历）+ CLI 跨端的**决策一致性中枢**，在有限 LLM 配额下做"高价值判断点 LLM 化 / Hot Path 零 LLM"的双路径架构
- 技术亮点：5 项—— W1–W15 不变量（W13 / W14 **在 DB 层强制**）/ 五维自适应遗忘 / Hot/Cold 双路径 / 决策可追溯（D1–D24）/ pre-commit + 集成测双层守卫 schema↔ORM 漂移

---

## 1. 我们对"记忆"的定义（挑战一回应）（~600 字）

> **填肉指引**：从 [01-CONSTITUTION §2](./01-CONSTITUTION.md) + [02-DESIGN §一](./02-DESIGN.md) 摘要、改写、加观点。

### 1.1 候选载体对比（4 选 1）
- 文档全文记忆（DocStore + RAG）：保原文、召回精准 / **致命缺陷**：无法处理两份文档互相覆盖；时序不可比
- 命令操作历史（OpHistory）：可重放、统计性强 / **致命缺陷**：无法承载跨人协同的决策；语义为空
- 通用知识图谱（General KG）：表达灵活 / **致命缺陷**：缺少时序与覆盖语义；无 provenance
- ★ **决策原子 + 演化谱系**（本设计选择）：同时承载时序、覆盖、跨源、可执行 / **代价**：提取成本高，需 LLM 辅助

### 1.2 我们的窄定义
**企业级记忆 = 带演化谱系、跨源共识度、五维时效衰减的决策原子集合。**
七字段构成：`(subject, predicate, object, timestamp, provenance, confidence, evolution_link)`

### 1.3 四属性硬约束（缺一不可）
1. **可时序对比** — 能回答"这条决策何时被推翻？"
2. **可覆盖追踪** — 能表达 SUPERSEDES / REFINES / GENERALIZES / BRANCHES 四类关系
3. **可跨源对齐** — 能判定群聊 / OKR / 文档说的是不是同一件事
4. **可机器执行** — 能让 CLI 基于这条决策做拦截或补全

### 1.4 与 LangMem 等通用框架的关系（站在巨人肩膀上）
- LangMem 解决"对话型 Agent 如何记住事"——单 Agent 单会话、自由 Fact、单一来源标签、覆盖/合并语义
- 我们的扩展：多人多源企业组织 / 结构化决策原子（七字段）/ SUPERSEDES-REFINES-BRANCHES-GENERALIZES / 六档 provenance 加权 / OpenClaw 双向钩入 CLI
- **复用策略**：短期 Thread Context 借鉴 LangMem；中长期决策记忆使用本文自研演化感知架构

### 1.5 为什么"窄定义"比"宽定义"更值
"宽定义"（员工产出的所有信息都是记忆）会沦为另一个搜索引擎；"窄定义"（决策原子）使系统能在**关键时刻主动干预**——这正是项目核心"产生实际效能"的核心要求。

---

## 2. 切入场景：飞书项目决策一致性（方向 B）（~400 字）

> **填肉指引**：从项目核心方向 B 描述 + [02-DESIGN §一.1.3](./02-DESIGN.md) 改写。

### 2.1 场景描述
飞书项目群聊 / 文档讨论 / OKR / 审批 / 妙记会议结论 / 日历 + 工程师 CLI 终端——决策与执行在不同**信道**之间产生、传播、覆盖；现状下没有任何系统能"记住所有决策的演化"。

### 2.2 典型痛点（3 个真实案例）
1. **决策被覆盖却无人察觉**：群聊里说"项目 A 5/15 上线"，OKR 仍写 5/1；CLI 部署时不知该信谁
2. **跨源不一致**：同一项目在 OKR、文档、群聊中描述 3 个版本
3. **CLI 拦截缺位**：开发者执行 `deploy --env=production`，没人提醒"Q3 已冻结发布"

### 2.3 为何选方向 B 而非 A/C
- 方向 A（CLI 高频命令补全）：已被 fish / atuin / zsh-autosuggestions 解决，重复造轮
- 方向 C（个人偏好隐式学习）：与"多人多源决策"主题不一致；隐式学习的副作用难承担
- ★ **方向 B**：企业核心痛点；技术上需要"演化追踪 + 跨源仲裁"两件没有现成方案的事；对外技术分享篇幅也最适合聚焦

---

## 3. 系统架构（数据流向图）（~800 字）

> **填肉指引**：从 [02-DESIGN §三](./02-DESIGN.md) 改写 + 嵌入 ASCII 架构图。

### 3.1 三环联动（概念层）
- **感知环 (Perception)**：从飞书全源 + CLI 事件中提取决策原子（Cold Path 承担）
- **决策环 (Decision)**：基于 Uncertainty / Consensus / Provenance 进行冲突判定 + 卡片策略分层（Hard 断言 / Soft 询问 / GHOST 静默）
- **记忆环 (Memory)**：以三层混合存储承载演化、覆盖、衰减、归档；通过 Hot Path 缓存对接 CLI 拦截与决策检索

### 3.2 五层架构（工程层）
```
[输入层] 飞书消息 / OKR / 审批 / 文档 / 妙记 / 日历 + CLI 事件
   ↓
[路由层] OpenClaw 决策-执行路由器（飞书 ↔ CLI 双向）
   ↓
[处理层] Hot Path (<200ms) | Cold Path (<3s)
         零 LLM 调用       | Doubao 选择性赋能
   ↓
[存储层] PostgreSQL 16 + pgvector + 自引用图层（v1 单库）
   ↓
[输出层] 飞书卡片 / 演化树 / 跨系统对齐 + CLI 拦截 / 注入 / 回写
```

### 3.3 关键架构决策（D1–D9 节选）
- **D1**：单亲演化模型（`decisions.parent_id` + `evolution_type`，5 enum 含 ROOT）
- **D4**：v1 = pgvector（不是 Qdrant），v2 切 Qdrant 触发条件已写宪法 §3.3
- **D6**：v1 = APScheduler（同进程内存），v2 切 Celery + Redis
- **D8**：docker-compose `pgvector/pgvector:pg16`
- **D11**：包管理 = uv（PEP 621 原生支持）

完整 D1–D24 决策追溯见附录 A。

### 3.4 Hot/Cold 双路径——在有限 LLM 配额下的必然性
- **资源约束（一等约束）**：Doubao TPM 1w 单人 / 3w 小组（火山引擎），派生约 10K calls/day
- **若 Hot Path 也走 LLM**：日均请求 50K 次将立刻击穿额度
- **解法**：80% 请求零 LLM（规则缓存 + 精确索引 + 本地向量）；20% 请求 Doubao 选择性赋能（提取 / 演化判定 / Reflect / 跨源对齐）
- **副效果**：跑得快 + 经济可行 + 演示稳定（不依赖网络）

---

## 4. 七大核心机制（~1200 字 — 最大份额）

> **填肉指引**：从 [02-DESIGN §四](./02-DESIGN.md) 改写；每个机制 ~170 字。**关键**：每个机制都要说"它解决了什么实际问题"，不只是技术描述。

### 4.1 机制一：全源跨系统一致性检测
- 6 数据源接入（消息 1.0 / OKR 0.95 / 审批 0.9 / 文档 0.85 / 妙记 0.7 / 日历 0.5），按信任权重仲裁
- 共识度公式：`C = Σ(w_i × match_i) / Σ(w_i)`
- **关键优化**：跨系统扫描只在精确索引命中后触发，避免对每条消息做 5 路 API 扫描，日均 API 调用从 ~50K 降至 ~5K

### 4.2 机制二：演化图谱（LLM 主路径 + 词表加速层）
- 5 类关系：ROOT / SUPERSEDES / REFINES / GENERALIZES / BRANCHES
- Doubao 2.0 演化判定 Prompt（输出 `{evolution_type, confidence, reasoning}`）
- **加速层**：OPPOSITE_PAIRS 词表（"冻结"vs"发布"等）命中时直接返回 (SUPERSEDES, 0.99)，跳过 LLM，**估算节省日均 30% 额度**

### 4.3 机制三：Reflect 自改进循环
- Cold Path 提取后，对**边界置信度**（0.5–0.85）的判定送 Reflect Agent
- 输出 `{quality_score, potential_missed_parent, suggested_type, confidence_calibration}`
- **额度敏感**：仅边界置信度调用，跳过高置信（>0.85）和低置信（<0.5），**估算节省日均 40% Reflect 调用**

### 4.4 机制四：Actor-Aware 溯源（六档信任）
- USER_STATED 1.0 / OKR_SYNCED 0.95 / APPROVAL_PASSED 0.9 / DOC_SYNCED 0.85 / MEETING_EXTRACTED 0.7 / SYSTEM_INFERRED 0.5
- 低信任来源（≤0.7）默认进 HYPOTHESIS，需高信任源确认或人工复核才转正

### 4.5 机制五：Hot/Cold 双路径
- Hot Path < 200ms：本地缓存命中 → 直接返回（**零 LLM 调用**）
- Cold Path < 3s：Doubao 选择性提取 + 判定 + Reflect
- **服务占比目标**：Hot 80% / Cold 20%
- 缓存策略：LRU + 5min TTL；Cold Path 结果实时写入缓存

### 4.6 机制六：Hard/Soft 卡片分层 + 双闸门
- 三态：HARD 断言 / SOFT 询问 / GHOST 静默
- **Gate 1 打扰预算**：每用户每日卡片推送上限 5 次（W14，**DB 层 CHECK 强制**）
- **Gate 2 工作时间窗**：仅 9:00–19:00 推送（紧急 CLI 拦截除外）
- 三态反馈：确认 → 覆写 + 刷 RAG / 否认 → 重置 uncertainty / 24h 无反馈 → 降权 STALE

### 4.7 机制七：五维上下文自适应遗忘
**核心公式**：
```
λ(t) = λ_base × f_freq × f_consensus × f_semantic × f_uncertainty × f_user_validation
new_uncertainty = clip(prev + λ(t) × Δt_days, 0, 1)
```
- 五条独立衰减通道（访问频次 / 跨源共识 / 语义中心性 / 置信不确定性 / 用户验证反馈）
- 乘性建模动机：**"任一通道告警都应加速遗忘"**，符合"短板效应"直觉
- 五级状态机：ACTIVE → STALE → HYPOTHESIS → GHOST → ARCHIVED
- 超参校准用 LLM（小样本场景）/ 大样本时切回归

---

## 5. 数据契约与不变量（~600 字）

> **填肉指引**：从 [03-SCHEMA](./03-SCHEMA.md) + [04-ENGUIDE §3 §8.11](./04-ENGUIDE.md) 改写。

### 5.1 数据三层
```
API DTO (pydantic)  ← feishu_integration / cli 边界用
   ↕ to_business / from_business
业务对象 (pydantic)  ← memory_engine 内部流通
   ↕ to_orm / from_orm
ORM (SQLAlchemy 2.0) ← 仅 memory_engine.models 触达
```

### 5.2 8 主表 + 6 enum + 状态机
- 主表：`decisions / decision_embeddings / cards / card_quota / users / reflect_logs / trace_log / decay_calculations`
- 6 enum：`provenance_enum / evolution_type_enum / decision_state_enum / card_type_enum / card_status_enum / card_response_enum`
- 状态机：5 态 + 7 类转换（ACTIVE → STALE → HYPOTHESIS → GHOST → ARCHIVED）

### 5.3 W1–W15 不变量（核心是"DB 层强制"两条）
| W | 不变量 | 实现层 |
|:---:|:---|:---|
| W2 | REFINES 父保 ACTIVE / SUPERSEDES 父转 ARCHIVED | App + 巡检 |
| W13 | 飞书 API 必记 trace_id | **DB（trace_log.trace_id PK NOT NULL）** |
| W14 | 单用户 5/日卡片上限 | **DB（card_quota.count CHECK ≤ max_daily）** |

W13 / W14 在 DB 层 CHECK 强制 = **应用 bug 也无法绕过**。这是宪法 §5.5 的最大价值。

### 5.4 异常树（25 类）
`MemoryEngineError` 根 → 6 大类（LLM / Feishu / DB / Invariant / Extraction / Config）→ 25 子类
所有异常含 `trace_id + extra` 属性，便于日志关联

---

## 6. 评测设计与承诺（~500 字）

> **填肉指引**：从 [06-benchmark-design](./06-benchmark-design.md) 改写。

### 6.1 三大主测试（项目核心强制项 + 宪法级承诺）
| TC | 名称 | 主架构目标 | Baseline 预期 |
|:---:|:---|:---:|:---:|
| TC001 | 抗干扰记忆召回 | **Recall_robust ≥ 90%** | ≤ 30% |
| TC002 | 矛盾更新覆写 | **Acc_supersede ≥ 95%** | ≤ 40% |
| TC003 | 跨源一致性检测 | 100% | < 10% |
| TC007+TC009 | 操作效能（时间 + 步数） | **E_align ≥ 60× / E_step ≥ 80%** | — |

**这些是"宪法级承诺"，不是"努力目标"**。任一项未达成 → 不可宣称该能力"已交付"。

### 6.2 测试矩阵 TC001-TC009
- 主测试组（TC001-TC003）：抗干扰 / 矛盾覆写 / 跨源
- 边界组（TC004-TC006）：时序错乱 / 模糊语义 / 低价值遗忘
- 效能组（TC007-TC009）：回答准确率 / 人工干预率 / 检索耗时（Hot ≤ 200ms / Cold ≤ 3s）

### 6.3 双系统对照（主架构 vs Baseline RAG）
- 唯一变量 = 记忆引擎实现；其他变量（LLM / Embedding / 上下文窗口）完全一致
- 评分公式：`主架构得分 = 三大主测试 × 0.7 + 边界 × 0.2 + 效能 × 0.1`
- 优势倍数目标 ≥ 2×

### 6.4 当前 fixture 状态
- **已建（v0.1）**：TC001（100 噪声 + 1 核心决策）、TC002（3 迭代 + 4 边界）—— NPU-src 贡献，[`benchmark/fixtures/`](../benchmark/fixtures/)
- **待建**：TC003 跨源（30 组）/ TC004-006 边界 / TC007 100 QA / TC008 干预统计 / TC009 1000 次延迟

---

## 7. 工程实施现状（~400 字）

> **填肉指引**：基于 [PROGRESS.md](../PROGRESS.md) Day 1–15 + ticket 完成度，**诚实陈述**已做 / 缺口。

### 7.1 阶段性交付的取舍
- 持续开发模式下，先 Phase 0（基础设施 + 数据层）后 Phase 1+（业务模块 + 跨源真接入）
- 取舍：先**深度**（设计 / 数据契约 / 不变量）后**广度**（业务实现 / 跨源真接入 / benchmark 跑分）
- 不变量在 DB 层强制 / pre-commit 漂移守卫 = "未来扩团队接手安全"

### 7.2 Phase 0 已就位（4/5）
| Ticket | 内容 | 状态 |
|:---|:---|:---:|
| T-001 | 项目基线 + 22 文件 + 71 包 + Docker PG | ✅ |
| T-002 | schema.sql 290 行 + ORM 437 + 异常 121；W2/W14 DB CHECK | ✅ |
| T-003 | types.py 361 + config.py 159 + 4 单测 627；73 unit passed | ✅ |
| T-004 | validate_consistency 250 + alembic 0001 49 + 5 集成测 137；schema↔ORM 双层守卫 | ✅ |
| T-005 | utils 层（LLM 网关 / 飞书 / 缓存 / 嵌入） | 进行中 / 部分 mock |

### 7.3 已知缺口（v1.0 未交付）
- M1–M7 业务模块：**全部未实施**（接口契约已定）
- LLM 真接入：架构对齐 Doubao 三档 EP，**未实跑**
- 飞书真接入：webhook 路由 / Bot 推送 **未实跑**
- 三大主测试：fixture 已建，**未跑分**
- 跨源（OKR / 审批 / 妙记 / 日历）：宪法 §3.3 已标 v1 fixture 模拟

### 7.4 诚实承诺
- **架构与数据契约**：已就位、可审计、扩团队接手 1 周内可在此基础上补完业务层
- **演示能力**：基础设施（schema / ORM / 验证 / 集成测）可现场演示；W2/W14 不变量违反触发可视化
- **LLM/飞书接入**：预留 1 周缓冲；实跑分预计 v1.1 交付

---

## 8. 为何这种记忆对企业有价值（~400 字）

> **填肉指引**：从 [02-DESIGN §一.1.3 + §二](./02-DESIGN.md) 改写 + 加商业角度。

### 8.1 解决的核心矛盾
**多人多源决策的演化与一致性** —— 这是企业级场景独有，个人场景不存在；现有任何记忆框架（LangMem 等）都不直接解决

### 8.2 不试图解决的（取舍声明）
- **个人命令历史**：fish / atuin / zsh-autosuggestions 已充分解决
- **通用知识图谱**：缺时序 + 缺 provenance，沦为搜索引擎
- **隐式偏好学习**：副作用难承担，与方向 B 主题不一致

### 8.3 商业可行性（非堆料 = 可部署）
- Hot Path 零 LLM 调用 → **95% 请求经济可行**
- Doubao 配额 TPM 1w 单人 / 3w 小组 → 派生 ~10K calls/day 已够企业演示
- LLM 额度耗尽自动降级本地 7B（W12）→ **永不 panic**

### 8.4 跨企业可复制性
- 飞书 → 钉钉 / Lark / Teams 等：schema.sql + 七大机制不变；只换 `feishu_integration` 适配层
- 飞书 → 自建 IM：同上
- v1 PG 单库底座 → v2 Qdrant + Neo4j + Celery + Redis 演进路径已明文（宪法 §3.3 Conditional Scope）

### 8.5 一句话商业价值
"决策一致性 + 演化追溯 + 跨源仲裁" 是**所有企业 SaaS 共同的痛点底座**；先在飞书生态打通，再迁移到任何企业 IM 都是配置工作。

---

## 附录 A：决策追溯（D1–D24）

> **填肉指引**：从 PROGRESS.md 的"决策"章节抽取；每条 ~30 字。

| # | 决策 | 选择 | 拍板时间 |
|:---:|:---|:---|:---:|
| D1 | 演化关系挂哪 | (a) `decisions.parent_id` + `evolution_type` 字段 | Day 6 |
| D2 | ROOT 是 enum 值还是隐式 | (a) ROOT 是 enum 值之一（5 值） | Day 6 |
| D3 | 跨源信息存哪 | (a) `consensus_sources` jsonb | Day 6 |
| D4 | v1 向量库 | (b) pgvector（不是 Qdrant） | Day 6 |
| D5 | W2 状态强制 | (b)+(c) 应用层 + 巡检 | Day 6 |
| D6 | v1 任务调度 | (b) APScheduler | Day 7 |
| D7 | Python 版本 | (b) 3.12 | Day 7 |
| D8 | Docker 提供方式 | (a) docker-compose.yml | Day 7 |
| D9 | 首业务 ticket | (a) M1+M2+M5 端到端切片 | Day 7 |
| D10 | LLM 模型分工（隐含） | Heavy = Doubao 2.0 / Light = 1.6 / Embedding v1 | Day 7 |
| D11 | 包管理工具 | (b) uv（不是 pip） | Day 7 |
| D12 | ORM 风格 | Mapped + DeclarativeBase（SQLAlchemy 2.0 现代式） | Day 10 |
| D13 | 异常类形态 | 含 trace_id + extra + 自定义 __str__ | Day 10 |
| D14 | schema.sql 组织 | 单文件（不切多文件） | Day 10 |
| D15 | updated_at 触发器 | PG BEFORE UPDATE TRIGGER（仅 3 张表） | Day 10 |
| D16 | pgvector 扩展 | schema.sql 头部 CREATE EXTENSION | Day 10 |
| D17 | 业务 enum vs ORM enum 位置 | 业务 enum 放 types.py，ORM enum 留 models.py | Day 13 |
| D18 | Decision.from_orm 实现 | model_validate(model, from_attributes=True) | Day 13 |
| D19 | Settings fail-fast | 5 必填 env 缺失即 raise ConfigError | Day 13 |
| D20 | 单测连真 PG？ | 不连（端到端 SQL 测留 T-004） | Day 13 |
| D21 | SQL 解析方式 | 正则（不引入 sqlparse） | Day 14 |
| D22 | alembic 0001 形式 | op.execute(schema.sql 整文件) | Day 14 |
| D23 | 集成测默认行为 | `addopts -m "not integration"` 默认跳；显式 `-m integration` 跑 | Day 14 |
| D24 | validate 形态 | 脚本（exit 1 + stderr）+ check() 函数双暴露 | Day 14 |

---

## 附录 B：W1–W15 不变量映射

> **填肉指引**：从 [03-SCHEMA §9](./03-SCHEMA.md) 直接复用。

| W | 不变量 | 实现层 |
|:---|:---|:---|
| W1 | 卡片有忽略按钮 + 来源链接 | UI |
| W2 | REFINES 父保 ACTIVE / SUPERSEDES 父转 ARCHIVED | App + 巡检 |
| W3 | 跨系统冲突优先级 > 单系统 | App |
| W4 | ARCHIVED 可检索不告警 | App |
| W5 | CLI 拦截失败默认放行 | App |
| W6 | Reflect 修改只影响未来 | App |
| W7 | Hot/Cold 5min 最终一致 | DB+App |
| W8 | 复议重置全量清零 | App |
| W9 | OKR 权重永远最高 | 配置 |
| W10 | Soft 高不确定走确认卡片 | App |
| W11 | 24h 内不重复推同一决策对 | DB+App |
| W12 | Doubao 额度耗尽切本地 | App |
| **W13** | **飞书 API 必记 trace_id** | **DB（NOT NULL PK）** |
| **W14** | **单用户 5/日卡片上限** | **DB（CHECK ≤ max_daily）** |
| W15 | 非工作时段暂停非紧急卡片 | App |

---

## 附录 C：M1–M7 接口契约总表（节选）

> **填肉指引**：从 [04-ENGUIDE §8](./04-ENGUIDE.md) 抽取关键接口签名（不展开 6 字段）；~25 个签名的 1 页摘要。

```python
# M1 提取
extract_from_message(msg) -> list[DecisionAtom]
extract_from_doc_change(change) -> list[DecisionAtom]

# M2 演化判定
find_potential_parents(candidate, top_k=3) -> list[Decision]
judge_evolution(candidate, parent) -> EvolutionJudgment
commit_evolution(child, parent, judgment) -> Decision

# M3 Reflect
should_reflect(judgment) -> bool
reflect(judgment, ctx) -> ReflectReport

# M4 Actor-Aware（数据规约，无函数）
PROVENANCE_TRUST_WEIGHTS / CONSENSUS_WEIGHTS

# M5 Hot Path
precise_match(subject, predicate=None) -> list[Decision]
semantic_search(query_embedding, top_k=5) -> list[(Decision, float)]
get_decision_by_id(id) -> Decision | None
query_active_decisions(subject, predicate=None) -> list[Decision]

# M5 Cold Path
process_event(event) -> ProcessResult

# M6 卡片
classify_conflict(a, b) -> ConflictLevel
decide_card_action(conflict, uncertainty) -> CardAction
enqueue_card(card) -> UUID
gate_check(user_id, card) -> GateResult
push_due_cards(user_id, limit=5) -> list[UUID]
record_response(card_id, response) -> None

# M7 衰减
compute_factors(decision) -> FiveFactors
recompute_uncertainty(decision_id, reason) -> float
batch_decay(max_rows=1000) -> int
handle_w8_reset(decision_id) -> None

# CLI
pre_command_hook(command, args, env) -> InterceptDecision
post_command_hook(command, args, exit_code, decision_ids) -> None
```

---

## 附录 D：文档版本历史与协作纪律

> **填肉指引**：从各 doc 的"附录 修订历史"章节聚合。

| 文档 | 当前版本 | 关键修订 |
|:---|:---:|:---|
| 01-CONSTITUTION | v1.3 | v1.0 初稿 → v1.1 D1/D4（向量+图层降至 PG）→ v1.2 D6（APScheduler）+ Doubao 资源刷新 → v1.3 双贡献者协作纪律（NPU-src 加入） |
| 02-DESIGN | v3.3.3 | v3.3 → v3.3.1 五维公式补 f_user_validation → v3.3.2 Seed-2.0 → Doubao 17 处 + TPM 框架 → v3.3.3 头部瘦身 + 附录修订历史 |
| 03-SCHEMA | v1.0.1 | v1.0 初稿 → v1.0.1 五因子永久锁定 + 附录 A T-004 启用 |
| 04-ENGUIDE | v1.0.1 | v1.0 初稿（25 接口契约）→ v1.0.1 §9.1 与 .env.example 对齐 |
| 06-benchmark-design | v1.0 | 初稿（整合自 NPU-src TEST_CASES_AB） |
| CLAUDE.md | v1.3 | v1.0 → v1.1 对齐 v3.3 + §2.8 PROGRESS 习惯 → v1.2 双贡献者 → v1.3 多人协作纪律 |

**协作纪律**（宪法 §10.3 + CLAUDE §3.1）：
- 每次 push 前先 `git pull origin main`
- 删文件前 grep 引用 + 跨贡献者确认（曾因没确认让 ARCHITECTURE.md / METRICS.md 复活两次）
- 目录归属以 04-ENGUIDE §1 为准
- 决策锁定走 surface 选项 + 推荐 + 字母锁定流程，全留 paper trail

---

## 附录 E：演示脚本 5 场景（节选）

> **填肉指引**：从 [02-DESIGN §九](./02-DESIGN.md) 节选——每个场景留 100 字 + 1 张时序图。

| 场景 | 演示要点 |
|:---|:---|
| 场景一 | 跨系统冲突检测（核心卖点）：群聊 + OKR + 文档三方冲突 → 飞书 Bot 卡片 8s 内推送 |
| 场景二 | CLI 实时拦截（技术壁垒）：`deploy --env=production` → Hot Path 200ms 红字拦截 |
| 场景三 | 五维自适应遗忘（数学优雅）：决策 A 高频 vs 决策 B 单源；7 天后 confidence 演化曲线 |
| 场景四 | 矛盾更新覆写（项目核心测试二）：A → B SUPERSEDES，状态机自动转换 |
| 场景五 | 决策原子全生命周期（端到端叙事）：诞生 → 演化 → Reflect → 复议 → 归档 |

---

## 状态与下一步

> 本文档当前状态：**v0.1 框架草稿**（2026-05-13 起草，~1500 字骨架 + ~3500 字 TODO 标记）
> 下一步：按 §0–§8 逐节填肉至目标字数；附录 A–E 按引用直接抽取；预计 8–10 小时完成 v1.0 终稿
> 终稿目标：5000 字主体 + 1500 字附录，可导出 PDF 作为项目对外公开交付物
