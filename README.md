# FeishuAI-STZ · 飞书决策一致性引擎

> 企业级长程协作记忆系统 · 飞书生态决策一致性中枢
> Team STZ

把企业级记忆**窄定义**为 **"带演化谱系、跨源共识度、五维时效衰减的决策原子集合"**，在飞书消息 / 文档 / OKR / 审批 / 妙记 / 日历 + CLI 之间做**一致性中枢**。

---

## ⭐ 30 秒看懂这个项目

| 维度 | 我们的做法 | 区别于 baseline |
|:---|:---|:---|
| **记忆单元** | 决策原子（7 字段：subject / predicate / object / timestamp / provenance / confidence / evolution_link） | 不是文档全文 / 不是命令历史 / 不是通用 KG |
| **演化语义** | 5 类关系（ROOT / SUPERSEDES / REFINES / GENERALIZES / BRANCHES）+ 状态机 5 态 | RAG 没有覆盖语义；通用 KG 缺时序 |
| **跨源仲裁** | 6 档 provenance + 共识度公式（`C = Σ(w_i × match_i) / Σ(w_i)`） | 无跨源对齐能力 |
| **时效衰减** | **五维乘性公式**：`λ(t) = λ_base × f_freq × f_consensus × f_semantic × f_uncertainty × f_user_validation` | 无遗忘机制 |
| **不变量** | **W13/W14 在 DB 层 CHECK 强制**（`chk_decisions_evolution_parent` / `chk_card_quota_count`） | 仅靠应用层维护，可被 bug 绕过 |
| **架构** | Hot/Cold 双路径（80% 请求**零 LLM 调用**，TPM 1w 单人配额下经济可行） | 全走 LLM，配额吃紧 |
| **工程纪律** | pre-commit 11 hooks + 集成测 5/5 + schema↔ORM 漂移自动守卫 | 文档与代码漂移无人盯 |
| **决策追溯** | **D1-D24 全程 paper trail**（surface→recommend→letter-lock 流程） | 决策淹没在 commit message 里 |

**已运行能力** ✅：92 单测 + 5 集成测全过 / mypy --strict 业务代码 0 error / pre-commit 11/11 全过 / pgvector 0.8.2 可用 / W2 W14 反向触发 IntegrityError 验过

**待补能力** ⚠️：M1–M7 业务模块 / Doubao 真接入 / 飞书 webhook / 三大主测试实跑分（架构与 mock 路径已就位，扩团队 1 周内可补完）

---

## 📦 提交答卷与文档

### 项目展示
- 📄 **[白皮书 v0.1](./docs/whitepaper.md)** — 5000 字框架（8 章 + 5 附录）
- 📊 **[评测设计](./docs/06-benchmark-design.md)** — TC001–TC009 测试矩阵 + 评分规则

### 设计文档（按阅读顺序）
| # | 文档 | 用途 | 行数 |
|:---:|:---|:---|:---:|
| — | [CLAUDE.md](./CLAUDE.md) | AI 协作行为约束（7 戒律） | ~250 |
| 01 | [01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) | 项目宪法（使命 / 范围 / W1-W15 不变量 / 评测承诺） | 412 |
| 02 | [02-DESIGN.md](./docs/02-DESIGN.md) | 架构设计（七大机制 + 五维遗忘 + Hot/Cold 双路径） | 768 |
| 03 | [03-SCHEMA.md](./docs/03-SCHEMA.md) | 数据契约（8 主表 + 6 enum + 状态机 + W 不变量映射） | 702 |
| 04 | [04-ENGUIDE.md](./docs/04-ENGUIDE.md) | 工程纲要（§8 接口契约总表 ~25 个函数签名） | 1096 |
| 06 | [06-benchmark-design.md](./docs/06-benchmark-design.md) | 评测设计（TC001-TC009 + 双系统对照） | 408 |

### 过程证据
- 🗂 **[PROGRESS.md](./PROGRESS.md)** — 每日工作记录（Day 6 → Day 16）
- 🎫 **[tickets/](./tickets/)** — T-001 ~ T-005 全程 ticket 草稿与实施轨迹
- 📜 **[git log](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commits/main)** — ~50 commits，全程 conventional commits

阅读顺序：CLAUDE → 01 → 02 → 03 → 04 → 06 → 当前 ticket。
（05-edge-discipline.md 待建——跨源 OKR/审批/妙记/日历真接入触发后才写。）

---

## 🚀 快速启动（WSL2 Ubuntu 24.04 + Python 3.12）

```bash
# 1. clone
cd ~ && git clone https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ.git
cd FeishuAI-STZ

# 2. 装齐生产 + 开发依赖（uv 自动建 venv + 锁版本）
uv sync --extra dev

# 3. 启动本地 PG 16 + pgvector 0.8.2
docker compose up -d postgres
docker compose ps                                # 确认 healthy

# 4. 装 git hooks（11 个，含 schema↔ORM 漂移检查）
uv run pre-commit install
uv run pre-commit run --all-files                # 全过

# 5. 跑全部单测（92 个）
uv run pytest -q                                  # 期望：92 passed in <1s

# 6. 跑集成测（5 个，testcontainers 起独立 PG）
uv run pytest -m integration                     # 期望：5 passed in ~6s

# 7. 验证 fixture 加载
uv run python -m benchmark.validate_fixtures
```

### 演示亮点命令

```bash
# DEMO 1: W2 不变量在 DB 层强制（应用 bug 也无法绕过）
docker compose exec -T postgres psql -U memory -d memory -c "
  INSERT INTO decisions (subject, predicate, object, logical_timestamp,
                         provenance, confidence, evolution_type)
  VALUES ('test', 'test', 'test', now(), 'USER_STATED', 0.9, 'SUPERSEDES');"
# → ERROR: chk_decisions_evolution_parent violation ✅

# DEMO 2: schema↔ORM 漂移检查
uv run python scripts/validate_consistency.py    # → "OK: 一致"
# 故意改 models.py 加字段 → 1 秒检测出来 → 还原 → 再 OK
```

---

## 📊 项目当前阶段

| Phase | 内容 | 状态 |
|:---:|:---|:---|
| **0/5** | T-001 项目基线 + 22 文件 + 71 包 + Docker PG | ✅ |
| **0/5** | T-002 schema.sql 290 行 + ORM 437 + 异常树 121 + W2/W14 DB CHECK | ✅ |
| **0/5** | T-003 types.py 361 + config.py 159 + 4 单测 627 | ✅ |
| **0/5** | T-004 validate_consistency 250 + alembic 0001 49 + 5 集成测 137 | ✅ |
| **0/5** | T-005 P0：invariants + cache + 19 单测 | ✅ |
| 0/5 | T-005 P1/P2：LLM gateway mock + embeddings hash-based + feishu mock | ⏳ |
| 1.1 | T-006 M1+M2+M5 端到端切片（webhook → cold_path → DB） | ⏸ |
| 1.2 | 三大主测试实跑分 | ⏸ |

详见 [PROGRESS.md](./PROGRESS.md)。

---

## 🛡 W1-W15 不变量速览

| # | 不变量 | 实现层 |
|:---:|:---|:---|
| W2 | REFINES 父保 ACTIVE / SUPERSEDES 父转 ARCHIVED | App + 巡检 + 集成测 |
| **W13** | **飞书 API 必记 trace_id** | **DB（trace_log.trace_id PK NOT NULL）** |
| **W14** | **单用户 5/日卡片上限** | **DB（card_quota.count CHECK ≤ max_daily）** |
| W15 | 非工作时段暂停非紧急卡片 | App（`assert_w15` + zoneinfo） |
| 其他 W | 见 [03-SCHEMA §9](./docs/03-SCHEMA.md) | DB / App / Config / UI 混合 |

**W13 / W14 在 DB 层 CHECK 强制 = 应用 bug 也无法绕过**。这是宪法 §5.5 的最大价值。

---

## 👥 团队（active 贡献者）

| 角色 / 子领地 | 承担者 | 负责模块 |
|:---|:---|:---|
| R3 文档体系 + R1 内核工程 | **[czhang076](https://github.com/czhang076)** | 4 文档体系 / T-001~T-005 P0 / AI 协作流程设计 |
| R3 评测数据 fixture | **NPU-src** | TC001/TC002 fixture / TEST_CASES_AB 设计 / Baseline RAG（test 分支）/ 飞书 API 调研 |
| AI 副驾（编码 / 文档 / 矛盾识别） | **Claude Code** | 95% 文档与代码"驾驶员"；架构推演 + 跨文档一致性检查 |

**协作纪律**（[宪法 §10.3](./docs/01-CONSTITUTION.md) + [CLAUDE §3.1](./CLAUDE.md)）：
- 每次 push 前 `git pull origin main`
- 删文件前 grep 引用 + 跨贡献者确认
- 决策走 surface→recommend→letter-lock，留 paper trail（D1-D24）
- 目录归属以 [04-ENGUIDE §1](./docs/04-ENGUIDE.md) 为准

---

## 📈 量化指标

```
5000 文档行（4 核心 doc + 06 + whitepaper 框架）
1800 业务代码行（T-002 ~ T-005 P0）
 900 测试代码行（unit + integration）
  92 单测全过 in 0.79s
   5 集成测全过 in 5.48s
  11 pre-commit hooks 全过（含 validate-consistency）
   0 mypy --strict 业务代码 error
  24 锁定决策（D1-D24，含选项 + 推荐 + 拍板）
  15 不变量（W1-W15，DB 强制 2 条）
 ~50 git commits
~200 AI 协作轮次（Claude Code）
   0 项目 LLM 生产调用（mock 模式 + 真接入预留）
```

---

## License

MIT
