# 03 · 数据模型规约 (Schema)

> **文档编号**：03-SCHEMA
> **版本**：v1.0
> **生效日期**：2026-04-27
> **上级文档**：[01-CONSTITUTION.md](./01-CONSTITUTION.md) v1.3
> **架构对齐**：[02-DESIGN.md](./02-DESIGN.md) v3.3-focused

---

## 0. 文档定位

### 0.1 本文是数据契约

- 描述 **PostgreSQL 16** 中必须存在的表、字段、枚举、约束、索引
- 描述五维衰减字段、状态机、不变量在 schema 上的落地位置
- **不**描述算法、Prompt、接口签名（归 02-DESIGN / 04-ENGUIDE）
- **不**描述测试 fixture（归 06-benchmark-design）

### 0.2 与代码的对应关系

```
03-SCHEMA.md  ──契约──►  schema.sql  ──契约──►  models.py
                              │
                              └──► validate_consistency.py 检查 schema.sql ↔ models.py 字段一一对应
```

任何字段不在本文中存在 → 该字段不合法。任何 schema.sql 与 models.py 漂移 → 阻塞 PR。

### 0.3 修改流程（CLAUDE.md §2.4 + 宪法 §0.3）

| 改动级别 | 流程 |
|:---|:---|
| 字段类型微调 / 注释补全 | 字段级，PR 即可 |
| 新增字段 / 索引 / 约束 | 条款级：先改本文 → 改 `schema.sql` → 改 `models.py` → 跑 `validate_consistency.py` → PR 描述写"改了 X 字段，原因 Y" |
| 新增表 / 删表 / 改主键 | 范围级：需 active 贡献者 ✅；走 Alembic 迁移；不可绕过 |

---

## 1. 实体关系总览

```
users ──┬─ owns N ──► decisions
        ├─ owns N ──► cards
        └─ owns N ──► card_quota

decisions ──┬─ self FK (parent_id) ──► decisions
            ├─ 1:1 ──► decision_embeddings    (decision_id PK)
            ├─ 1:N ──► reflect_logs
            └─ 1:N ──► decay_calculations

cards ──┬─ N:1 ──► decisions  (主决策)
        └─ N:0..1 ──► decisions  (related_decision_id, 冲突对的另一方)

trace_log ── 独立表，由 cards.trace_id 引用
```

主表 8 张（含 `decision_embeddings`）；其中 `decay_calculations` 标记为"可裁剪审计日志"，但答辩展示价值高，强烈建议保留。

---

## 2. 枚举类型

### 2.1 `provenance_enum`（六档信任来源，对齐 02-DESIGN §四 机制四）

| 值 | 信任权重 | 说明 |
|:---|:---:|:---|
| `USER_STATED` | 1.00 | 用户在群聊 / CLI 显式陈述 |
| `OKR_SYNCED` | 0.95 | 飞书 OKR 同步 |
| `APPROVAL_PASSED` | 0.90 | 飞书审批正式通过 |
| `DOC_SYNCED` | 0.85 | 飞书文档正式段落 |
| `MEETING_EXTRACTED` | 0.70 | 妙记 / 会议纪要提取 |
| `SYSTEM_INFERRED` | 0.50 | LLM 从自由对话推断 |

> 权重值不入 enum，由应用层配置常量 `PROVENANCE_TRUST_WEIGHTS` 提供（一处定义，多处复用）。

### 2.2 `evolution_type_enum`（演化关系，5 值）

| 值 | parent_id | 说明 | W2 影响 |
|:---|:---:|:---|:---|
| `ROOT` | NULL | 全新决策，无父节点 | — |
| `SUPERSEDES` | NOT NULL | 与父决策对立，覆盖父决策 | **父转 ARCHIVED** |
| `REFINES` | NOT NULL | 细化父决策，不覆盖 | 父保 ACTIVE |
| `GENERALIZES` | NOT NULL | 泛化父决策（罕见） | 父保 ACTIVE |
| `BRANCHES` | NOT NULL | 与父决策并存，无覆盖关系 | 父保 ACTIVE |

CHECK 约束（在 `decisions` 表上）：
```sql
CHECK (
  (evolution_type = 'ROOT' AND parent_id IS NULL)
  OR
  (evolution_type IN ('SUPERSEDES','REFINES','GENERALIZES','BRANCHES')
   AND parent_id IS NOT NULL)
)
```

### 2.3 `decision_state_enum`（5 态状态机）

| 值 | 说明 |
|:---|:---|
| `ACTIVE` | 当前生效 |
| `STALE` | uncertainty ≥ 0.7 但未被复议 |
| `HYPOTHESIS` | 低 provenance 提取，待高信任源确认 |
| `GHOST` | 长期未访问 + 无验证；可检索不告警 |
| `ARCHIVED` | 终态：被 SUPERSEDES 或人工归档（W4 可检索不告警） |

### 2.4 `card_type_enum`

| 值 | 触发条件 |
|:---|:---|
| `HARD_ASSERTION` | conflict_level = HARD |
| `SOFT_INQUIRY` | SOFT 且 uncertainty > 0.7 |
| `GHOST_LOG` | SOFT 且 uncertainty ≤ 0.7（仅记录） |
| `CROSS_SYSTEM_ALERT` | M1 跨源冲突 |
| `EVOLUTION_NOTICE` | SUPERSEDES 后告知 |

### 2.5 `card_status_enum`

| 值 | 说明 |
|:---|:---|
| `QUEUED` | 入队，待推送（受 W14/W15 闸门拦截） |
| `PUSHED` | 已推送，等待响应 |
| `RESPONDED` | 已收到响应 |
| `EXPIRED` | 24 h 无响应（→ 派生 W11 去重判据） |

### 2.6 `card_response_enum`

| 值 | 说明 |
|:---|:---|
| `CONFIRMED` | 用户确认 |
| `DENIED` | 用户否认 |
| `NO_RESPONSE_24H` | 24 h 无响应 |
| `IGNORED` | 用户主动忽略 |

### 2.7 `source_type`（在 `consensus_sources` jsonb 内，不入 SQL enum）

字符串集合：`feishu_message / feishu_okr / feishu_approval / feishu_doc / feishu_minutes / feishu_calendar / cli_event`

应用层校验，不在 DB 强制（jsonb 灵活性优先，便于未来加源不动 schema）。

---

## 3. 表 schema 详述

> 字段表统一字段：`字段 | 类型 | NN（NOT NULL） | 默认 | 注释`

### 3.1 `decisions`（决策原子主表）

**用途**：承载决策原子的七字段 + 状态 + 五维衰减跟踪 + 跨源证据 + 演化关系。

| 字段 | 类型 | NN | 默认 | 注释 |
|:---|:---|:---:|:---|:---|
| `decision_id` | uuid | ✓ | `gen_random_uuid()` | PK；显示层渲染为 `dec_<short>` |
| `subject` | varchar(255) | ✓ | — | 决策主语 |
| `predicate` | varchar(255) | ✓ | — | 决策谓词（自由文本，不做 enum 限定） |
| `object` | text | ✓ | — | 决策对象 |
| `logical_timestamp` | timestamptz | ✓ | — | 决策被提出的逻辑时间（消息原始时间） |
| `extracted_at` | timestamptz | ✓ | `now()` | 系统提取时间 |
| `provenance` | provenance_enum | ✓ | — | 主来源 |
| `confidence` | numeric(3,2) | ✓ | — | [0.00, 1.00]；CHECK |
| `uncertainty` | numeric(3,2) | ✓ | `0.00` | [0, 1]；五维衰减输出 |
| `state` | decision_state_enum | ✓ | `'ACTIVE'` | — |
| `parent_id` | uuid | — | NULL | FK → decisions.decision_id（自引用），W8 复议时清空 |
| `evolution_type` | evolution_type_enum | ✓ | — | **必填，无默认值**（CLAUDE.md §1.1 规范）；与 parent_id 联动（§2.2） |
| `consensus_sources` | jsonb | ✓ | `'[]'::jsonb` | 数组：`[{source_type, uri, weight, extracted_at}]` |
| `consensus_score` | numeric(3,2) | ✓ | `0.00` | 跨源共识度，应用层计算后写入 |
| `source_event_id` | text | — | NULL | 主源事件 ID，例如 `feishu://group/xxx/msg/yyy` |
| `original_text` | text | — | NULL | 原文摘录，便于答辩举证 |
| `access_count` | int | ✓ | `0` | 五维 f_freq 输入 |
| `last_accessed_at` | timestamptz | ✓ | `now()` | 五维 f_freq 输入 |
| `confirm_count` | int | ✓ | `0` | 五维 f_user_validation 输入 |
| `last_confirmed_at` | timestamptz | — | NULL | — |
| `last_decay_calc_at` | timestamptz | ✓ | `now()` | 上次 λ 重算时间 |
| `business_impact` | numeric(3,2) | ✓ | `0.50` | 卡片优先级权重；CHECK [0, 1] |
| `owner_user_id` | varchar(64) | — | NULL | FK → users.user_id |
| `created_at` | timestamptz | ✓ | `now()` | — |
| `updated_at` | timestamptz | ✓ | `now()` | 由 `BEFORE UPDATE` 触发器维护 |

**约束**：
- PK: `decision_id`
- FK: `parent_id` → `decisions.decision_id` **ON DELETE RESTRICT**（不允许误删带子节点的决策）
- FK: `owner_user_id` → `users.user_id` ON DELETE SET NULL
- CHECK: `evolution_type` × `parent_id` 联动（见 §2.2）
- CHECK: `confidence`, `uncertainty`, `consensus_score`, `business_impact` ∈ [0, 1]
- CHECK: `access_count >= 0 AND confirm_count >= 0`

**索引**：
| 索引名 | 字段 | 用途 |
|:---|:---|:---|
| `idx_decisions_subj_pred_state` | (subject, predicate, state) | Hot Path 精确索引（02-DESIGN §四 机制一） |
| `idx_decisions_state_decay` | (state, last_decay_calc_at) | 五维批量重算扫描 |
| `idx_decisions_owner_state` | (owner_user_id, state) WHERE state IN ('ACTIVE','STALE','HYPOTHESIS') | 用户面板 |
| `idx_decisions_parent` | (parent_id) WHERE parent_id IS NOT NULL | 多跳查询 |
| `idx_decisions_fts` | GIN(to_tsvector('simple', subject \|\| ' ' \|\| predicate \|\| ' ' \|\| object)) | 备用全文模糊搜索 |

**触及不变量**：W2, W4, W6, W8, W9, W10

---

### 3.2 `cards`（推送卡片）

**用途**：承载所有推送给用户的卡片记录，支持 W11（24 h 去重）与 W14（5/日预算）。

| 字段 | 类型 | NN | 默认 | 注释 |
|:---|:---|:---:|:---|:---|
| `card_id` | uuid | ✓ | `gen_random_uuid()` | PK |
| `user_id` | varchar(64) | ✓ | — | FK → users |
| `decision_id` | uuid | ✓ | — | FK → decisions（卡片主决策） |
| `related_decision_id` | uuid | — | NULL | FK → decisions（冲突对的另一方） |
| `card_type` | card_type_enum | ✓ | — | — |
| `status` | card_status_enum | ✓ | `'QUEUED'` | — |
| `priority_score` | numeric(3,2) | ✓ | `0.00` | confidence × business_impact |
| `response` | card_response_enum | — | NULL | 仅 status='RESPONDED' 时非空 |
| `pushed_at` | timestamptz | — | NULL | NULL 表示未推送 |
| `responded_at` | timestamptz | — | NULL | — |
| `trace_id` | varchar(64) | — | NULL | FK → trace_log |
| `created_at` | timestamptz | ✓ | `now()` | — |

**约束**：
- PK: `card_id`
- CHECK: `(status='RESPONDED') = (response IS NOT NULL)` — 状态与响应一致
- CHECK: `(status IN ('PUSHED','RESPONDED','EXPIRED')) = (pushed_at IS NOT NULL)`

**索引**：
| 索引名 | 字段 | 用途 |
|:---|:---|:---|
| `idx_cards_user_status` | (user_id, status) | 队列扫描 |
| `idx_cards_dedup` | (decision_id, related_decision_id, pushed_at) WHERE status IN ('PUSHED','RESPONDED') | W11 24 h 去重 |

**触及不变量**：W1（UI 层）, W10, W11, W14（联 card_quota）, W15（应用层）

---

### 3.3 `card_quota`（每日打扰预算 W14）

**用途**：单用户每日卡片推送上限（W14）的原子计数器。

| 字段 | 类型 | NN | 默认 | 注释 |
|:---|:---|:---:|:---|:---|
| `user_id` | varchar(64) | ✓ | — | 复合 PK 之一 |
| `quota_date` | date | ✓ | — | 复合 PK 之二（用户本地时区日期） |
| `count` | int | ✓ | `0` | CHECK BETWEEN 0 AND `max_daily` |
| `max_daily` | int | ✓ | `5` | 默认 5；可调但 CHECK 必须保留 |
| `updated_at` | timestamptz | ✓ | `now()` | — |

**约束**：
- PK: `(user_id, quota_date)`
- FK: `user_id` → `users.user_id`
- CHECK: `count >= 0 AND count <= max_daily` — **W14 在 DB 层强制**

**触及不变量**：**W14（DB 层强制，无法绕过）**

---

### 3.4 `users`（用户档案）

**用途**：用户基础属性 + 工作时间窗（W15）。

| 字段 | 类型 | NN | 默认 | 注释 |
|:---|:---|:---:|:---|:---|
| `user_id` | varchar(64) | ✓ | — | PK；内部 ID |
| `feishu_user_id` | varchar(128) | — | NULL | 飞书 open_id；UNIQUE |
| `name` | varchar(128) | ✓ | — | — |
| `email` | varchar(255) | — | NULL | — |
| `timezone` | varchar(64) | ✓ | `'Asia/Shanghai'` | IANA 时区名 |
| `work_hour_start` | smallint | ✓ | `9` | CHECK BETWEEN 0 AND 23 |
| `work_hour_end` | smallint | ✓ | `19` | CHECK BETWEEN 1 AND 24 AND > work_hour_start |
| `is_active` | boolean | ✓ | `true` | — |
| `created_at` | timestamptz | ✓ | `now()` | — |
| `updated_at` | timestamptz | ✓ | `now()` | — |

**索引**：
- UNIQUE `idx_users_feishu_id` ON (feishu_user_id) WHERE feishu_user_id IS NOT NULL

**触及不变量**：W15（应用层读 work_hour_*）

---

### 3.5 `reflect_logs`（Reflect 质量档案）

**用途**：M3 Reflect Agent 的判定记录与质量分数；未来用于离线 prompt 优化（v2 演进项）。

| 字段 | 类型 | NN | 默认 | 注释 |
|:---|:---|:---:|:---|:---|
| `log_id` | uuid | ✓ | `gen_random_uuid()` | PK |
| `decision_id` | uuid | ✓ | — | FK → decisions |
| `parent_id` | uuid | — | NULL | FK → decisions（被判定时的父） |
| `original_evolution_type` | evolution_type_enum | — | NULL | 判定前的类型 |
| `quality_score` | numeric(3,2) | ✓ | — | [0, 1]；< 0.7 → "待复核" |
| `potential_missed_parent_id` | uuid | — | NULL | FK → decisions |
| `suggested_type` | evolution_type_enum | — | NULL | Reflect 建议 |
| `confidence_calibration` | numeric(4,3) | ✓ | `0.000` | 范围 [-1, 1]；可负 |
| `reasoning` | varchar(255) | — | NULL | ≤ 200 字（02-DESIGN §四 机制二 prompt 约束） |
| `evaluated_at` | timestamptz | ✓ | `now()` | — |

**约束**：
- PK: `log_id`
- CHECK: `quality_score BETWEEN 0 AND 1`
- CHECK: `confidence_calibration BETWEEN -1 AND 1`

**索引**：
- `idx_reflect_decision_time` ON (decision_id, evaluated_at DESC)
- `idx_reflect_quality` ON (quality_score) — 质量直方图查询

**触及不变量**：W6（Reflect 仅写本表，绝不 UPDATE `decisions.evolution_type` 历史值，由应用层保证）

---

### 3.6 `trace_log`（飞书 API trace，W13）

**用途**：W13 强制 —— 所有飞书 API 调用必须记录 trace_id。

| 字段 | 类型 | NN | 默认 | 注释 |
|:---|:---|:---:|:---|:---|
| `trace_id` | varchar(64) | ✓ | — | PK；应用层生成（uuid hex） |
| `api_endpoint` | varchar(255) | ✓ | — | e.g. `/open-apis/im/v1/messages` |
| `direction` | varchar(8) | ✓ | — | CHECK IN ('OUT','IN','HOOK') |
| `request_payload` | jsonb | — | NULL | OUT 方向有；IN 方向 NULL |
| `response_payload` | jsonb | — | NULL | — |
| `http_status` | smallint | — | NULL | — |
| `latency_ms` | int | — | NULL | — |
| `called_at` | timestamptz | ✓ | `now()` | — |
| `error_message` | text | — | NULL | — |

**约束**：
- PK: `trace_id`
- CHECK: `direction IN ('OUT','IN','HOOK')`

**索引**：
- `idx_trace_called_at` ON (called_at DESC) — 演示时查最近调用链
- `idx_trace_endpoint` ON (api_endpoint, called_at DESC)

**触及不变量**：**W13（DB 层 NOT NULL `trace_id` 强制；应用层无 trace 即 raise）**

---

### 3.7 `decay_calculations`（五维 λ 审计日志）

**用途**：记录每次 uncertainty 重算的输入因子，供答辩展示（决策生命周期曲线）与离线参数校准。

| 字段 | 类型 | NN | 默认 | 注释 |
|:---|:---|:---:|:---|:---|
| `calc_id` | uuid | ✓ | `gen_random_uuid()` | PK |
| `decision_id` | uuid | ✓ | — | FK → decisions |
| `lambda_value` | numeric(6,4) | ✓ | — | λ(t) 输出 |
| `f_freq` | numeric(3,2) | ✓ | — | 五因子之一 |
| `f_consensus` | numeric(3,2) | ✓ | — | — |
| `f_semantic` | numeric(3,2) | ✓ | — | — |
| `f_uncertainty` | numeric(3,2) | ✓ | — | — |
| `f_user_validation` | numeric(3,2) | ✓ | — | **见 §5.1 注释** |
| `prev_uncertainty` | numeric(3,2) | ✓ | — | 重算前 |
| `new_uncertainty` | numeric(3,2) | ✓ | — | 重算后 |
| `reason` | varchar(64) | ✓ | — | `periodic_batch` / `access_event` / `cross_source_conflict` / `user_response` |
| `calculated_at` | timestamptz | ✓ | `now()` | — |

**索引**：
- `idx_decay_decision_time` ON (decision_id, calculated_at DESC)
- `idx_decay_time` ON (calculated_at DESC) — 全局时间扫描

**裁剪策略**：本表是审计日志，不写入也不影响主功能。但**强烈建议保留**——答辩时展示"决策 A 的 uncertainty 在 7 天内的演化曲线"是核心数据，是评测报告的关键证据。

---

### 3.8 `decision_embeddings`（pgvector v1）

**用途**：决策原子的语义向量；v1 用 pgvector 与决策同库。

| 字段 | 类型 | NN | 默认 | 注释 |
|:---|:---|:---:|:---|:---|
| `decision_id` | uuid | ✓ | — | PK；FK → decisions ON DELETE CASCADE |
| `embedding` | vector(1024) | ✓ | — | 默认 1024 维（Doubao Embedding v1）；改维度需新迁移 |
| `model_name` | varchar(64) | ✓ | — | e.g. `doubao-embedding-v1` |
| `model_version` | varchar(32) | — | NULL | — |
| `generated_at` | timestamptz | ✓ | `now()` | — |

**索引**：
- HNSW: `idx_emb_hnsw` ON (embedding vector_cosine_ops) WITH (m=16, ef_construction=64) — 近邻查询

**v2 切换条件**（宪法 §3.3）：单 collection > 1M 向量 OR 近邻 P95 > 200ms 时切 Qdrant；届时本表保留为 PG 侧备份。

> **维度选择**：1024 = Doubao Embedding v1（已确认 2026-04-27）。改维度需新建迁移并清空已有 embedding 重新生成。

---

## 4. 状态机

### 4.1 5 态总览

```
   ┌─[insert: high conf+high prov]──► ACTIVE ◄──[user CONFIRMED]─┐
   │                                    │                         │
   │                                uncertainty ≥ 0.7             │
   │                                    │                         │
   │                                    ▼                         │
   │   ┌─[insert: low conf]──►       STALE ─────────────────────┘
   │   │                              │
   │   ▼                       long inactive +
   │ HYPOTHESIS                no validation
   │   │                              │
   │   │  [verified by                ▼
   │   │   high prov src]           GHOST ◄──┐
   │   └────────────────► ACTIVE     │       │
   │                                  │ archive
   │                                  │ trigger
   │                                  ▼       │
   │   ┌──[SUPERSEDED by another]──► ARCHIVED │
   │                                          │
   └──────────────────────────────────────────┘
   (W4: ARCHIVED 可检索不告警)
```

### 4.2 转换触发清单

| 转换 | 触发条件 | 实现位置 |
|:---|:---|:---|
| → `ACTIVE` | INSERT 且 confidence ≥ 0.85 且 provenance ∈ {USER_STATED, OKR_SYNCED, APPROVAL_PASSED} | App |
| → `HYPOTHESIS` | INSERT 且 confidence < 0.7 OR provenance = SYSTEM_INFERRED | App |
| `ACTIVE` → `STALE` | uncertainty ≥ 0.7 | App + 巡检 |
| `STALE` / `HYPOTHESIS` → `ACTIVE` | 用户 CONFIRMED（W8 全量清零） | App |
| `STALE` / `HYPOTHESIS` → `GHOST` | last_accessed_at < now()-30d AND confirm_count = 0 | 巡检（每日 1 次） |
| `GHOST` → `ARCHIVED` | last_accessed_at < now()-90d | 巡检 |
| ANY → `ARCHIVED` | 被另一决策 SUPERSEDES（W2） | App + 巡检 |

### 4.3 实现位置原则（D5 决策 = b+c）

- **应用层**（`memory_engine/state_machine.py`）：所有正向转换由该模块单点调用
- **DB 层 CHECK**：仅约束当前 state 与其他字段一致性，不强制状态机
- **巡检任务**（`scripts/invariant_check.py`，每 1 min）：扫描 W2/W4 在数据上是否成立，违反就告警，**不自动修复**

> **不使用 PG 触发器**：触发器在 17 天周期内调试不友好；状态机是业务逻辑，不该藏在 SQL 触发器里。

---

## 5. 五维衰减字段映射

### 5.1 公式（02-DESIGN §四 机制七）

```
λ(t) = λ_base × f_freq × f_consensus × f_semantic × f_uncertainty × f_user_validation
new_uncertainty = clip(prev_uncertainty + λ(t) × Δt_days, 0, 1)
```

> **⚠️ 与 02-DESIGN 不一致点（需澄清）**：02-DESIGN §四 机制七的**公式**只列了 4 个因子（不含 f_user_validation），但**乘性建模动机**那段描述了 5 条独立衰减通道（含"用户验证反馈"）。本规约采纳 5 因子版本，原因是：
> 1. 02-DESIGN 描述部分明确说"五个因子建模五条独立的衰减通道"
> 2. 用户验证应是独立信号，不应混入 confidence 通道
> 3. 决策矩阵 D5 的"诚实先于自洽"原则要求显式表达
>
> **请确认**采纳 5 因子，并在 02-DESIGN §四 机制七公式上加 `× f_user_validation`；或反之，告知我把 f_user_validation 列从 `decay_calculations` 表移除并合并进 f_uncertainty 通道。

### 5.2 字段映射

| 因子 | schema 输入字段 | 计算逻辑（应用层） |
|:---|:---|:---|
| `f_freq` | `decisions.access_count`, `decisions.last_accessed_at` | 越多近期访问 → f 越低（保鲜） |
| `f_consensus` | `decisions.consensus_score` | 跨源共识高 → f 低 |
| `f_semantic` | `decision_embeddings.embedding` | 语义中心性（与所属簇中心的余弦） |
| `f_uncertainty` | `decisions.confidence` | 置信度低 → f 高（加速衰减） |
| `f_user_validation` | `decisions.confirm_count`, `decisions.last_confirmed_at` | 验证多 → f 低 |

每次重算：写一行 `decay_calculations` + UPDATE `decisions.uncertainty` + UPDATE `decisions.last_decay_calc_at`。

### 5.3 写入时机

| 触发 | 频率 | 动作 |
|:---|:---|:---|
| 用户访问决策 | 实时 | UPDATE access_count++, last_accessed_at = now() |
| 用户响应卡片 | 实时 | UPDATE confirm_count++, last_confirmed_at = now()；CONFIRMED 时触发 W8 全量清零 |
| 跨源新证据到达 | 实时 | UPDATE consensus_sources jsonb；重算 consensus_score |
| 五维批量重算 | Celery beat 每 1 min | 扫 `last_decay_calc_at < now() - interval '1 min'` AND state ∈ ('ACTIVE','STALE','HYPOTHESIS')；重算 uncertainty；写 decay_calculations |

### 5.4 W8（复议重置全量清零）SQL 模板

```sql
-- 用户 CONFIRMED 后，应用层调用：
UPDATE decisions
SET uncertainty       = 0.00,
    access_count      = 0,
    confirm_count     = confirm_count + 1,
    last_confirmed_at = now(),
    last_decay_calc_at = now(),
    state             = 'ACTIVE',
    updated_at        = now()
WHERE decision_id = $1;

-- 同步写一条 decay_calculations 行，reason='user_response'
INSERT INTO decay_calculations (
  decision_id, lambda_value,
  f_freq, f_consensus, f_semantic, f_uncertainty, f_user_validation,
  prev_uncertainty, new_uncertainty, reason
) VALUES ($1, 0.0, 0, 0, 0, 0, 0, $2, 0.00, 'user_response');
```

> `confirm_count` 不清零（保留为长期价值证据）；其他衰减相关字段全清零，符合 W8 "全量清零"。

---

## 6. 向量层

### 6.1 v1 = pgvector（默认）

启用扩展：
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

表：见 §3.8 `decision_embeddings`。

索引：
```sql
CREATE INDEX idx_emb_hnsw
  ON decision_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

近邻查询样例：
```sql
SELECT d.decision_id, d.subject, d.predicate, d.object,
       1 - (e.embedding <=> $1) AS cosine_similarity
FROM decisions d
JOIN decision_embeddings e USING (decision_id)
WHERE d.state = 'ACTIVE'
ORDER BY e.embedding <=> $1
LIMIT 5;
```

### 6.2 v2 = Qdrant（条件触发，宪法 §3.3）

切换条件：单 collection > 1M 向量 OR 近邻查询 P95 > 200ms。

切换时：
- Collection 命名：`decisions_v1`（按 schema 版本）
- 维度：与 §3.8 一致（默认 1024）
- 距离：cosine
- payload schema：`{decision_id, state, predicate, last_decay_calc_at}`（仅过滤所需）
- 同步：PG 是 source of truth，PG → Qdrant 异步双写

详细 collection 定义在切换 PR 中给出，本文不预先编写。

---

## 7. 图层

### 7.1 v1 = `decisions.parent_id` 自引用

`decisions` 表通过 `parent_id` + `evolution_type` 直接承载演化关系；不需要独立 edges 表。

多跳查询（recursive CTE 样例）：

```sql
-- 查决策 X 的完整演化谱系（祖先链）
WITH RECURSIVE ancestors AS (
  SELECT decision_id, parent_id, evolution_type, 0 AS depth
  FROM decisions
  WHERE decision_id = $1

  UNION ALL

  SELECT d.decision_id, d.parent_id, d.evolution_type, a.depth + 1
  FROM decisions d
  JOIN ancestors a ON d.decision_id = a.parent_id
  WHERE a.depth < 10  -- 防呆深度上限
)
SELECT * FROM ancestors;
```

### 7.2 v2 = Neo4j Community / Kuzu（条件触发，宪法 §3.3）

切换条件：多跳 ≥ 4 跳频繁出现 OR 多跳 P95 > 500ms。

- Node：`Decision { decision_id, state, subject, predicate, object }`
- Edge：`SUPERSEDES / REFINES / GENERALIZES / BRANCHES { confidence, created_at }`
- 同步：PG 是 source of truth，Neo4j 仅为查询加速器

---

## 8. 一致性

### 8.1 v1 单库无 W7 延迟

v1 只有 PostgreSQL 单库（含 pgvector），所有写入在同一事务内 commit，无 5 min 最终一致性问题 —— **W7 在 v1 自动满足，零延迟**。

### 8.2 v2 多库切换后

切换 Qdrant / Neo4j 后：
- 写：PG commit → 发事件到 Redis Stream → Worker 异步写副本库
- 失败重试：指数退避，3 次失败后告警，**但不阻塞 PG**
- 读：默认从 PG；性能敏感查询走副本库
- 一致性窗：≤ 5 min（W7）；超过则巡检告警

---

## 9. 不变量在 schema 上的实现位置

| W | 不变量 | 实现层 | 具体落地 |
|:---|:---|:---:|:---|
| W1 | 卡片有忽略按钮 + 来源链接 | UI | 应用层卡片渲染模板 |
| W2 | REFINES 父保 ACTIVE / SUPERSEDES 父转 ARCHIVED | App + 巡检 | `state_machine.on_evolution()` + `invariant_check.py` |
| W3 | 跨系统冲突优先级 > 单系统 | App | `priority_score` 计算时跨系统加成 |
| W4 | ARCHIVED 可检索不告警 | App | 卡片推送前 `WHERE state != 'ARCHIVED'` |
| W5 | CLI 拦截失败默认放行 | App | CLI hook 异常 → return 0 |
| W6 | Reflect 修改只影响未来 | App | Reflect 只 INSERT `reflect_logs`，不 UPDATE 决策历史值 |
| W7 | Hot/Cold 5 min 最终一致 | DB+App | v1 同库自动满足；v2 异步队列 + 巡检 |
| W8 | 复议重置全量清零 | App | §5.4 SQL 模板 |
| W9 | OKR 权重永远最高 | 配置 | `CONSENSUS_WEIGHTS` 常量（OKR=0.4 顶档） |
| W10 | Soft 高不确定走确认卡片 | App | `card_type` 决策树 |
| W11 | 24 h 内不重复推同一决策对 | DB+App | `idx_cards_dedup` + 应用层查询 |
| W12 | Doubao 额度耗尽切本地 | App | `utils.heavy_llm_extract` 内的额度计数器 |
| W13 | 飞书 API 必记 trace_id | **DB** | `trace_log.trace_id` PK NOT NULL；应用层无 trace 即 raise |
| W14 | 单用户 5/日卡片上限 | **DB** | `card_quota.count` CHECK ≤ `max_daily` |
| W15 | 非工作时段暂停非紧急卡片 | App | 推送前查 `users.work_hour_*`；hard 拦截 W15 不阻 |

**DB 层强制（不可绕过）**：W13, W14
**App 层为主**：W2, W3, W5, W6, W8, W10, W12, W15
**配置常量**：W9
**UI 层**：W1
**混合**：W4, W7, W11

---

## 10. 迁移与版本

### 10.1 工具：Alembic

不引入新依赖（Alembic 在 sqlalchemy 生态内，已隐含于未来的 `requirements.txt`）。

### 10.2 命名规范

```
migrations/versions/
  0001_initial_schema.py        ← 创建 §3 全部表 + enum + index + triggers
  0002_add_pgvector_ext.py      ← 启用 pgvector
  0003_add_decision_embeddings.py
  ...
```

### 10.3 v1.0 初始迁移内容清单

`0001_initial_schema.py` 必须创建：
- 6 个 SQL enum（§2.1–§2.6；2.7 不入 enum）
- 7 主表（decisions / cards / card_quota / users / reflect_logs / trace_log / decay_calculations）
- 全部 CHECK / FK / 索引
- `BEFORE UPDATE` 触发器维护各表 `updated_at`

`0002_add_pgvector_ext.py`：
- `CREATE EXTENSION vector`
- 创建 `decision_embeddings` 表
- HNSW 索引

### 10.4 改动顺序铁律（CLAUDE.md §2.4 + 宪法 §5.3）

```
[1] 改本文 03-SCHEMA.md
[2] 改 schema.sql （或新建 Alembic 迁移）
[3] 改 models.py
[4] 跑 python validate_consistency.py
[5] PR 描述：改了 X 字段，原因 Y
```

任一步骤跳过 = 不合规，PR 禁止合并。

---

## 附录 A：`validate_consistency.py` 规约

脚本必须检查：

1. `schema.sql` 中每张表 ↔ `models.py` 中每个 Model 类，1:1 对应
2. 每张表的字段名、类型、NOT NULL、DEFAULT、CHECK 约束在 Python 侧 1:1 对应
3. 所有 SQL enum 的取值集合在 Python `enum.Enum` 中完整存在且无多余值
4. 所有 FK 在 Python relationship 中显式声明
5. 所有索引在 Python `__table_args__` 中存在

退出码：
- `0` = 一致
- `1` = 漂移；stdout 列出每个不一致项（表名、字段、左右差异）

CI 必须挂此脚本；预期未来 `04-ENGUIDE.md §10` 给出 GitHub Actions 配置。

---

## 附录 B：命名约定

| 维度 | 约定 |
|:---|:---|
| 表名 | snake_case，复数形式（`decisions` 而非 `decision`） |
| 字段名 | snake_case |
| 主键 | `<表名单数>_id`（`decision_id` / `card_id`） |
| 时间字段 | 一律 `_at` 后缀，`timestamptz` 类型 |
| 布尔字段 | `is_` / `has_` 前缀 |
| 枚举值 | UPPER_SNAKE_CASE |
| 索引 | `idx_<表>_<语义>` |
| 外键约束 | `fk_<表>_<外键字段>` |
| Enum 类型名 | `<语义>_enum`（`provenance_enum` / `decision_state_enum`） |

---

## 附录 C：版本历史

| 版本 | 日期 | 变更 |
|:---|:---|:---|
| v1.0 | 2026-04-27 | 初稿。锁定 7 主表 + 1 向量表（共 8）；W13 / W14 在 DB 层强制；v1 = pgvector + PG 自引用；五维公式补 `f_user_validation` 因子并标记需 02-DESIGN 同步澄清 |
