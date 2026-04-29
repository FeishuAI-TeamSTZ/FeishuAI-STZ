# FeishuAI-STZ · 飞书决策一致性引擎

> 飞书 AI 校园挑战赛 · 题二（企业级记忆引擎）· **方向 B**：项目决策与上下文记忆
> Team STZ · 17 天交付窗口 (2026-04-22 → 2026-05-14)

把企业级记忆定义为 **"带演化谱系、跨源共识度、五维时效衰减的决策原子集合"**，在飞书消息 / 文档 / OKR / 审批 / 妙记 / 日历 + CLI 之间做一致性中枢。

---

## 文档导航

| # | 文档 | 用途 |
|:---:|:---|:---|
| — | [CLAUDE.md](./CLAUDE.md) | AI 协作行为约束 |
| — | [PROGRESS.md](./PROGRESS.md) | 工作记录（每会话追加） |
| 01 | [docs/01-CONSTITUTION.md](./docs/01-CONSTITUTION.md) | 项目宪法（使命 / 范围 / 不变量 / 评测承诺） |
| 02 | [docs/02-DESIGN.md](./docs/02-DESIGN.md) | 架构设计（七大机制 + 五维遗忘 + Hot/Cold 双路径） |
| 03 | [docs/03-SCHEMA.md](./docs/03-SCHEMA.md) | 数据模型规约（8 主表 + 状态机） |
| 04 | [docs/04-ENGUIDE.md](./docs/04-ENGUIDE.md) | 工程实施纲要（§8 接口契约总表） |
| 06 | [docs/06-benchmark-design.md](./docs/06-benchmark-design.md) | 评测设计（TC001–TC009） |

阅读顺序：先 CLAUDE → 01 → 02 → 03 → 04 → 当前 ticket。

---

## 快速启动（WSL2 Ubuntu 24.04 + Python 3.12）

```bash
# 1. clone（如果还没）
cd ~ && git clone https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ.git
cd FeishuAI-STZ

# 2. 装齐依赖（uv 自动建 venv + 解锁版本）
uv sync --extra dev

# 3. 启动本地 PG + pgvector
docker compose up -d postgres
docker compose ps                       # 确认 healthy

# 4. 验证 fixture 加载（无需 venv 激活，stdlib 即可）
python3 -m benchmark.validate_fixtures

# 5. 装 git hooks
uv run pre-commit install
uv run pre-commit run --all-files       # ruff + mypy 全过

# 6. 跑测试（当前 0 个，骨架就位）
uv run pytest -q
```

任一步报错请贴回 [Issue](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/issues) 或 PR 描述。

---

## 当前阶段

- ✅ 文档体系完工（01–04 + 06）
- ✅ T-001 项目基线 + 包结构（pyproject.toml + Docker + pre-commit）
- ⏳ T-002 数据层（schema.sql + ORM）→ 下一步
- ⏳ T-003 迁移 + 一致性脚本
- ⏳ T-004 utils 工具层
- ⏳ T-005 业务模块 + 接入层 stub
- ⏳ Phase 1.1 M1+M2+M5 端到端切片

详见 [PROGRESS.md](./PROGRESS.md)。

---

## 团队（active 贡献者）

| 角色 / 子领地 | 承担者 |
|:---|:---|
| 文档 / 架构 / Schema / 工程指南 / Ticket | **czhang076** |
| 评测数据 fixture（benchmark/fixtures/） | **NPU-src** |
| AI 副驾（编码 / 文档 / 矛盾识别） | **Claude Code** |

详见 [宪法 §10.2](./docs/01-CONSTITUTION.md)。

---

## License

MIT
