# 06 · 评测设计 (Benchmark Design)

> **文档编号**：06-benchmark-design
> **版本**：v1.0
> **生效日期**：2026-04-29
> **上级文档**：[01-CONSTITUTION.md](./01-CONSTITUTION.md) v1.3 §8 评测承诺
> **架构对齐**：[02-DESIGN.md](./02-DESIGN.md) v3.3-focused §六 三大测试 + 支撑指标
> **接口契约**：[04-ENGUIDE.md](./04-ENGUIDE.md) v1.0 §8（fixture 调用对应模块）
> **数据来源**：本文整合自 NPU-src 在 commit 418431f 推送的 `TEST_CASES_AB.md`，重组为标准化文档结构

---

## 0. 文档定位

### 0.1 是什么 / 不是什么

- 描述**测试用例（TCxxx）+ 评分规则 + fixture 数据规范 + 评测运行器入口**
- 不描述算法（归 02-DESIGN）；不描述 fixture 数据本身（归 `benchmark/fixtures/*.py`）；不描述测试代码（归 `benchmark/test_*.py`，T-005 实现）

### 0.2 评测原则（双系统对比）

所有用例在 **主架构** 与 **传统 RAG Baseline** 上**完全复用**，唯一变量为记忆引擎实现；其他变量（LLM 模型、Embedding 模型、上下文窗口、参数配置）**完全一致**。

### 0.3 与宪法承诺值的对照（核心）

| 宪法 §8 承诺 | 对应 TC | 目标 |
|:---|:---|:---:|
| Recall_robust ≥ 90% | TC001 | ≥ 90% |
| Acc_supersede ≥ 95% | TC002 | ≥ 95% |
| E_align ≥ 60× / E_step ≥ 80% | TC007 + TC009 | ≥ 60× / ≥ 80% |
| S3 Hot Path ≤ 200ms | TC009 | ≤ 200ms |
| S4 Cold Path ≤ 3s | TC009 | ≤ 3s |
| S5 自适应遗忘精准度 ≥ 80% | TC006 | ≥ 80% |
| S6 主动确认有效率 ≥ 75% | TC008（反向） | ≤ 5 次干预 / 7 天 |

---

## 1. 测试矩阵

| TC | 名称 | 类别 | 主架构目标 | Baseline 预期 | fixture 状态 |
|:---:|:---|:---|:---:|:---:|:---:|
| TC001 | 抗干扰记忆召回 | 三大主测试 | ≥ 90% | ≤ 30% | v0.1（NPU-src，100 噪声）→ v1.0 需扩到 1000 |
| TC002 | 矛盾更新覆写 | 三大主测试 | ≥ 95% | ≤ 40% | v0.1（NPU-src，3 迭代 + 4 边界） |
| TC003 | 跨源一致性检测 | 三大主测试 | 100% | < 10% | 待建 |
| TC004 | 时序错乱处理 | 边界 | 100% | 50% | 待建 |
| TC005 | 模糊语义查询 | 边界 | ≥ 90% | ≤ 60% | 待建 |
| TC006 | 低价值记忆遗忘 | 边界 | 100% | 0%（同等权重） | 待建 |
| TC007 | 回答准确率 | 效能 | ≥ 85% | ≤ 55% | 待建 |
| TC008 | 人工干预率 | 效能 | ≤ 5 / 7d | ≥ 15 / 7d | 待建 |
| TC009 | 检索耗时（P95） | 效能 | Hot ≤ 200ms / Cold ≤ 3s | ≤ 500ms | 待建 |

---

## 2. 三大主测试（赛题强制）

### 2.1 TC001 — 抗干扰记忆召回

| 项 | 内容 |
|:---|:---|
| **目标** | 验证大噪声下长期关键决策的召回能力 |
| **协议** | 1) 注入 1 条关键决策：`项目A 上线日期定在 2026-05-15`（来源：群聊 @负责人确认）<br>2) 注入 N=1000 条无关噪声：30% 闲聊 / 30% 技术讨论 / 30% 其他独立决策 / 10% 乱码或图片<br>3) 模拟 7 天时间流逝（无任何相关操作）<br>4) 触发查询：`项目A 什么时候上线？` |
| **评估标准** | 返回结果包含正确日期 `2026-05-15` 即为通过 |
| **指标** | `Recall_robust = 通过次数 / 测试轮数`，目标 ≥ 90%（10 轮容许 1 漏召） |
| **支撑机制** | 03-SCHEMA `idx_decisions_subj_pred_state` 精确索引 + pgvector 语义召回 + 五维遗忘 `f_freq` 项保护关键决策 |
| **fixture** | [`benchmark/fixtures/tc001_anti_interference.py`](../benchmark/fixtures/tc001_anti_interference.py) |
| **当前 fixture 状态** | v0.1（NPU-src 实现，100 噪声）→ **T-005 需扩展到 1000 噪声**以达赛题协议 |

### 2.2 TC002 — 矛盾更新覆写

| 项 | 内容 |
|:---|:---|
| **目标** | 验证决策迭代时返回最新版本的准确率 + 状态机 W2 正确触发 |
| **协议** | 1) 注入初始决策 A：`周报每周五发给张三`<br>2) 间隔 1h 注入 B：`周报以后发给李四，不用发张三了`<br>3) 间隔 1d 注入 C：`周报调整为每周四发给李四，抄送给张三`<br>4) 触发查询：`周报现在要发给谁？` |
| **评估标准** | 返回 C 的最新规则 `每周四发给李四，抄送给张三` 即为通过；A、B 状态应为 `ARCHIVED`，C 为 `ACTIVE` |
| **指标** | `Acc_supersede = 正确覆写次数 / 矛盾对总数`，目标 ≥ 95% |
| **边界场景**（必覆盖） | (i) 跨源矛盾：群聊说 A、文档写 B → provenance 仲裁<br>(ii) 时序错乱：B 先收到 / A 后收到 → logical_timestamp 仲裁<br>(iii) 软冲突：A "主要发给张三" / B "也抄送李四" → REFINES 而非 SUPERSEDES，A 保 ACTIVE<br>(iv) 多跳覆盖：A→B（SUPERSEDES）→ C（SUPERSEDES B）→ A、B = ARCHIVED，C = ACTIVE |
| **支撑机制** | 04-ENGUIDE §8.2 `judge_evolution` + `commit_evolution`；03-SCHEMA W2 不变量 |
| **fixture** | [`benchmark/fixtures/tc002_contradiction.py`](../benchmark/fixtures/tc002_contradiction.py) |
| **当前 fixture 状态** | v0.1（NPU-src，3 迭代 + 4 边界） |

### 2.3 TC003 — 跨源一致性检测

| 项 | 内容 |
|:---|:---|
| **目标** | 验证多源冲突信息的识别 + 共识度计算 |
| **协议** | 1) 飞书 OKR 同步：`Q3 冻结重大版本发布`<br>2) 飞书文档同步：`项目A 计划 Q4 上线`<br>3) 群聊新消息：`项目A 下周发 2.0 版本`<br>4) 触发查询：`项目A 下周能发版吗？` |
| **评估标准** | 主架构识别 2 处冲突（vs OKR / vs 文档）并提示优先级（OKR 最高，0.95）；Baseline 仅按检索分数返回最近一条 |
| **指标** | 冲突识别率：主架构目标 100%，Baseline 预期 < 10% |
| **支撑机制** | 04-ENGUIDE §8.4 `consensus_sources` jsonb + `CONSENSUS_WEIGHTS` 配置常量（W9：OKR 顶档） |
| **fixture** | `benchmark/fixtures/tc003_cross_source.py`（**待建**，T-005 实现） |
| **赛事映射** | 02-DESIGN §四 机制一 全源跨系统一致性检测的端到端验证 |

---

## 3. 边界场景测试

### 3.1 TC004 — 时序错乱处理

| 项 | 内容 |
|:---|:---|
| **目标** | 验证 logical_timestamp 而非接收时间的时序对齐 |
| **协议** | 1) 先收到延迟消息（发送时间 T-3 天）：`项目A 上线时间改为 5 月 20 日`<br>2) 后收到新消息（发送时间 T-1 天）：`项目A 上线时间确定为 5 月 15 日`<br>3) 查询：`项目A 最终上线时间是哪天？` |
| **评估标准** | 返回 5 月 15 日（按 logical_timestamp 排序，不按 extracted_at）|
| **指标** | 主架构目标 100%；Baseline 预期 50% |
| **fixture** | `benchmark/fixtures/tc004_temporal.py`（待建） |

### 3.2 TC005 — 模糊语义查询

| 项 | 内容 |
|:---|:---|
| **目标** | 验证非精确关键词查询的召回 |
| **协议** | 1) 注入决策：`项目A 上线前必须通过安全渗透测试`<br>2) 模糊查询：`项目A 发版前有什么强制流程吗？` |
| **评估标准** | 返回结果提到"安全渗透测试" |
| **指标** | 主架构 ≥ 90%；Baseline ≤ 60% |
| **支撑机制** | pgvector HNSW 近邻 + provenance 加权 |
| **fixture** | `benchmark/fixtures/tc005_fuzzy.py`（待建） |

### 3.3 TC006 — 低价值记忆遗忘

| 项 | 内容 |
|:---|:---|
| **目标** | 验证长期未访问低价值信息的自动降级（五维遗忘 M7） |
| **协议** | 1) 注入两条决策：<br>&nbsp;&nbsp;A（高价值）：`Q3 冻结发布`（多源确认 + 高频访问）<br>&nbsp;&nbsp;B（低价值）：`临时活动下周奶茶买一送一`（单源 + 无验证）<br>2) 模拟 30 天无访问<br>3) 分别查询 |
| **评估标准** | A 正常返回（state = ACTIVE）；B 提示"信息可能已过期"或 state ∈ {GHOST, ARCHIVED} |
| **指标** | S5 自适应遗忘精准度 ≥ 80%；本测试目标主架构 100% 正确降级，Baseline 0%（同等权重返回） |
| **支撑机制** | 04-ENGUIDE §8.8 五维衰减 + 状态机 4.2 转换规则 |
| **fixture** | `benchmark/fixtures/tc006_decay.py`（待建） |

---

## 4. 效能测试

### 4.1 TC007 — 回答准确率（综合）

| 项 | 内容 |
|:---|:---|
| **目标** | 在 100 条企业场景常见查询（含 40% 冲突 / 迭代场景）上对比双系统 |
| **协议** | 100 条人工标注查询 → 跑双系统 → 人工评分 |
| **指标** | 主架构 ≥ 85%；Baseline ≤ 55% |
| **fixture** | `benchmark/fixtures/tc007_qa_set.py`（待建） |

### 4.2 TC008 — 人工干预率（产品维度）

| 项 | 内容 |
|:---|:---|
| **目标** | 模拟 7 天使用，含 20 次决策迭代 / 冲突场景；统计需要人工纠正的次数 |
| **指标** | 主架构 ≤ 5 次；Baseline ≥ 15 次 |
| **支撑机制** | 04-ENGUIDE §8.7 卡片闸门 W14（5/日）+ M3 Reflect 边界自审 |
| **fixture** | `benchmark/fixtures/tc008_intervention.py`（待建） |

### 4.3 TC009 — 检索耗时（P95）

| 项 | 内容 |
|:---|:---|
| **目标** | 1000 次随机查询的 P95 延迟 |
| **协议** | 跑 1000 次查询 → 统计 P95 |
| **指标** | 主架构 Hot Path P95 ≤ **200ms** / Cold Path P95 ≤ **3s**；Baseline ≤ 500ms |
| **支撑机制** | 04-ENGUIDE §8.5 `precise_match` / `semantic_search`；五分钟 LRU 缓存 |
| **fixture** | `benchmark/fixtures/tc009_latency.py`（待建） |
| **宪法对应** | S3 Hot Path ≤ 200ms / S4 Cold Path ≤ 3s |

---

## 5. 测试数据集规范

### 5.1 总体构成（赛事级目标）

| 类型 | 目标数量 | 当前 | 说明 |
|:---|:---:|:---:|:---|
| 核心决策 | 100 条 | TC001+TC002 共 4 条 | 项目 / 规则 / 人员等各类型决策 |
| 迭代决策对 | 50 组 | TC002 内 3 迭代 | 同一条决策多次修改的序列 |
| 跨源冲突对 | 30 组 | 0 | 不同来源的冲突信息 |
| 噪声消息 | 10 000 条 | TC001 内 100 条 | 真实企业群聊脱敏数据（建议从飞书脱敏样本） |

差距：当前 fixture 基线已建（TC001/TC002 v0.1），但远低于赛事级目标。**T-005 拓展为 P0 任务**。

### 5.2 fixture 数据契约

`benchmark/fixtures/tcXXX_<name>.py` 必须 export：

| 变量名 | 类型 | 说明 |
|:---|:---|:---|
| `CORE_DECISION` | dict | 核心决策（含 content / key / expected_answer / source / timestamp） |
| `NOISE_MESSAGES` *(if applicable)* | list[dict] | 噪声消息（含 type / content / timestamp） |
| `DECISION_SEQUENCE` *(for TC002+)* | list[dict] | 决策迭代序列（含 id / content / expected_state） |
| `BOUNDARY_CASES` *(if applicable)* | list[dict] | 边界场景（含 name / description / expected_behavior） |
| `QUERIES` | list[dict] | 查询用例（含 query / expected_value / pass_criterion） |
| `TEST_CONFIG` | dict | 测试配置（pass_threshold / simulation_days / ...） |

新增 TC 时，在本节追加一行说明该 TC 的额外 export。

### 5.3 fixture 命名

```
benchmark/fixtures/
  tc001_anti_interference.py      ← 类别：抗干扰
  tc002_contradiction.py          ← 类别：矛盾覆写
  tc003_cross_source.py           ← 待建
  ...
```

**规则**：`tcNNN_<lowercase_short_name>.py`，与本文 §1 测试矩阵的 TC 编号对齐。

### 5.4 数据来源 + 许可

- v0.1 数据：NPU-src 自创（[commit 418431f](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/418431f)）；项目内自由复用
- 后续扩展：可基于飞书脱敏样本 / 公开数据集（如 ChatGLM 中文对话集）；引入新数据时在 §5.4 增条溯源注释

---

## 6. fixture 验证

### 6.1 [`benchmark/validate_fixtures.py`](../benchmark/validate_fixtures.py)

**用途**：快速 sanity check fixture 是否能正确加载、字段是否完整、数据量是否符合预期。

**运行方式**：
```bash
# 在仓库根目录
python -m benchmark.validate_fixtures
# 或
python benchmark/validate_fixtures.py
```

**输出**：每个 TC 的核心数据概览（CORE_DECISION / 噪声分布 / 迭代序列 / 边界场景）。

### 6.2 加新 fixture 时必更新

每新增一个 `tcXXX_<name>.py`，必须：
1. 在 `validate_fixtures.py` 加 import + 概览打印段
2. 在本文 §1 测试矩阵更新该 TC 的 fixture 状态（待建 → v0.x）
3. 在 PR 描述说明数据规模 + 来源

---

## 7. 评测运行器（待 T-005 实现）

`benchmark/runner.py`（暂未存在，T-005 ticket 创建）期望接口：

```python
def run_test(tc_id: str, system: Literal["main", "baseline"]) -> TestResult: ...
def run_all(systems: list[str] = ["main", "baseline"]) -> BenchmarkReport: ...
```

`TestResult` 字段：
- tc_id, system, pass_count, total_count, pass_rate
- p95_latency_ms, errors, raw_logs

`BenchmarkReport` 字段：
- 所有 TC 结果聚合
- 主架构 vs Baseline 优势倍数（目标 ≥ 2×，见 §8 评分规则）

---

## 8. 评分规则

```
主架构得分 = 三大主测试得分 × 0.7 + 边界测试得分 × 0.2 + 效能得分 × 0.1
Baseline 得分 = 同公式
优势倍数 = 主架构得分 / Baseline 得分

目标：优势倍数 ≥ 2×
```

**单 TC 得分计算**：
- TC 通过 → 1.0
- TC 部分通过（含 boundary 子项） → 子项加权平均
- TC 失败 → 0.0

**类别加权**：
- 三大主测试组：TC001 + TC002 + TC003 等权
- 边界组：TC004 + TC005 + TC006 等权
- 效能组：TC007 + TC008 + TC009 等权

---

## 9. 与 04-ENGUIDE §8 接口的对应

| TC | 调用的 §8 接口 |
|:---|:---|
| TC001 | `query_active_decisions` (§8.5) → `precise_match` + `semantic_search` |
| TC002 | `extract_from_message` (§8.1) → `judge_evolution` (§8.2) → `commit_evolution` (§8.2) → `query_active_decisions` (§8.5) |
| TC003 | 上述全链路 + `consensus_score` 计算（M1 in cold_path） |
| TC004 | `extract_from_message` 时遵循 `logical_timestamp`（M1） |
| TC005 | `semantic_search` (§8.5) 带模糊查询 embedding |
| TC006 | `recompute_uncertainty` + `batch_decay` (§8.8) |
| TC007 | 全链路 + 人工评分 |
| TC008 | `decide_card_action` + `gate_check` (§8.7) |
| TC009 | 计时 wrapper 包装 §8.5 / §8.6 接口 |

---

## 附录 A：当前 fixture 状态

| TC | 状态 | 说明 |
|:---:|:---|:---|
| TC001 | v0.1（NPU-src） | 100 噪声 + 1 核心决策 + N 查询 → **T-005 需扩到 1000 噪声** |
| TC002 | v0.1（NPU-src） | 3 决策迭代 + 4 边界场景 |
| TC003 | 待建 | 跨源冲突，预计 30 组 |
| TC004 | 待建 | 时序错乱，10 组 |
| TC005 | 待建 | 模糊查询，30 组 |
| TC006 | 待建 | 30 天遗忘场景 |
| TC007 | 待建 | 100 条 QA 集 |
| TC008 | 待建 | 7 天 20 次干预 |
| TC009 | 待建 | 1000 次延迟测试 |

---

## 附录 B：版本历史

| 版本 | 日期 | 变更 |
|:---|:---|:---|
| v1.0 | 2026-04-29 | 初稿。整合自 NPU-src 在 commit 418431f 推送的 `TEST_CASES_AB.md`；TC001-TC009 完整保留；fixture 路径迁到 `benchmark/fixtures/`（04-ENGUIDE §1 对齐）；与宪法 §8 承诺值显式对照；接口与 04-ENGUIDE §8 一一映射 |
