# T-001：项目基线 + 包结构

> **类型**：Phase 0 骨架 ticket（系列 1/5）
> **领地**：R1 内核工程师
> **优先级**：P0（阻塞所有后续 ticket）
> **计划用时**：半天
> **关联 §8 接口**：无（基线 ticket）
> **触及不变量**：无
> **预算豁免**：CLAUDE.md §6 ≤5 文件 → 本 ticket ~14 文件，理由见下
> **依据文档**：[CLAUDE.md](../CLAUDE.md) §0 §2.1 §6；[01-CONSTITUTION](../docs/01-CONSTITUTION.md) §3.3 D6（APScheduler）；[04-ENGUIDE](../docs/04-ENGUIDE.md) §1 §2 §9 §10

---

## 1. 目标

让以下命令在 **WSL2 Ubuntu 24.04 + Python 3.12** 环境下零错误执行：

```bash
uv sync                          # 装齐生产 + 开发依赖
pre-commit install               # 启用 git hooks
pre-commit run --all-files       # ruff format + ruff check + mypy --strict 全过
docker compose up -d postgres    # PG 16 + pgvector 起来
pytest tests/ -q                 # 收集到 0 个测试但退出码 0
```

完成后，仓库具备**所有后续代码 ticket 开工的基础设施**，但**不含任何业务逻辑**。

---

## 2. 范围

### 2.1 In Scope（必做）

**项目元数据 + 工具配置**（7 文件）：
- `pyproject.toml` — Python 3.12 项目元数据 + 全部依赖（生产 12 包 + 开发 9 包，对齐 04-ENGUIDE §10）
- `.python-version` — 锁 3.12
- `.env.example` — 占位环境变量（DATABASE_URL / DOUBAO_* / FEISHU_*，对齐 04-ENGUIDE §9.1）
- `.gitattributes` — 行尾规约（统一 LF；.bat/.ps1 保留 CRLF）
- `.pre-commit-config.yaml` — ruff format / ruff check / mypy --strict
- `alembic.ini` — 迁移工具配置
- `docker-compose.yml` — `pgvector/pgvector:pg16` 单服务（D8）

**包结构**（~10 文件 `__init__.py`）：
- `memory_engine/__init__.py` & `memory_engine/utils/__init__.py`
- `feishu_integration/__init__.py`
- `cli/__init__.py`
- `benchmark/__init__.py` & `benchmark/fixtures/__init__.py`
- `tests/__init__.py` & `tests/unit/__init__.py` & `tests/integration/__init__.py` & `tests/fixtures/__init__.py`
- `scripts/__init__.py`
- `migrations/__init__.py`

**测试 + 迁移占位**（3 文件）：
- `conftest.py`（根）— pytest 共享 fixture 入口（v1 内容仅 docstring）
- `migrations/env.py` — Alembic environment（最小占位，连接串读环境变量）
- `migrations/versions/.gitkeep` — 占位

**修改**（1 文件）：
- `README.md` — 替换原 1 行内容，加快速启动 + 文档导航

**总计**：约 21 个文件（包含 ~10 个空 `__init__.py`），**实质内容文件 11 个**，约 350 行。

### 2.2 Out of Scope（明确不做，分给后续 ticket）

| 不做 | 归属 ticket |
|:---|:---:|
| `memory_engine/models.py` ORM | T-002 |
| `memory_engine/types.py` pydantic 业务对象 | T-002 |
| `memory_engine/exceptions.py` 异常树 | T-002 |
| `memory_engine/config.py` 常量 | T-002 |
| `schema.sql` 源头 SQL | T-002 |
| `migrations/versions/0001_initial_schema.py` | T-003 |
| `migrations/versions/0002_add_pgvector_ext.py` | T-003 |
| `scripts/validate_consistency.py` | T-003 |
| `memory_engine/utils/llm_gateway.py` 等真实现 | T-004 |
| M1–M7 业务模块 stub | T-005 |
| `feishu_integration/*` & `cli/*` 真实现 | T-005 |
| GitHub Actions CI 配置 | T-001 完成后单独 ticket |

### 2.3 预算豁免说明（CLAUDE.md §6）

| 维度 | 上限 | 本 ticket | 豁免理由 |
|:---|:---:|:---:|:---|
| 文件数 | ≤ 5 | ~21 | 一次建立目录结构 + 工具链；每文件 < 50 行；拆分反而难审；后续 ticket 都受益于一次性建立 |
| 行数 | ≤ 500 | ~350 | 不超 |
| LLM 调用 | ≤ 50 | 0 | 纯模板生成 |
| 测试时长 | ≤ 60s | < 5s（pytest 0 测试） | 不超 |

---

## 3. 依赖清单（写入 `pyproject.toml`）

### 3.1 Production
```
sqlalchemy >=2.0,<3
alembic >=1.13,<2
pydantic >=2.5,<3
pydantic-settings >=2.1,<3
fastapi >=0.110,<1
uvicorn[standard] >=0.27,<1
httpx >=0.27,<1
structlog >=24.1,<25
psycopg[binary] >=3.1,<4
pgvector >=0.2,<1
cachetools >=5.3,<6
apscheduler >=3.10,<4         # D6: v1 任务调度
```

### 3.2 Dev
```
pytest >=8.0,<9
pytest-mock >=3.12,<4
pytest-cov >=4.1,<5
testcontainers[postgres] >=4.0,<5
respx >=0.20,<1
freezegun >=1.4,<2
ruff >=0.4,<1
mypy >=1.10,<2
pre-commit >=3.6,<4
```

合计 21 包，全部锁 major 版本（`<X+1`）。

---

## 4. 关键决策（已锁，不重新讨论）

- **D6 = APScheduler**（宪法 §3.3）→ 用 apscheduler 不用 celery
- **D7 = Python 3.12**（pyproject `requires-python = ">=3.12,<3.13"`）
- **D8 = docker-compose.yml**（PG 16 + pgvector 单服务，端口 5432）
- **D11 = uv**（不是 pip）→ pyproject.toml 走 PEP 621 标准，uv 原生支持
- **同步代码风格**（04-ENGUIDE §2）→ 不装 pytest-asyncio

---

## 5. DoD（完成判定）

- [ ] 全部文件已创建，行数 ±20% 内
- [ ] `uv sync` 装齐 21 包，无版本冲突
- [ ] `pre-commit install` 成功
- [ ] `pre-commit run --all-files` 退出码 0（注：当前无 .py 业务文件，仅 ruff/mypy 跑空跑过）
- [ ] `docker compose up -d postgres` 启动；`docker compose ps` 显示 healthy
- [ ] `docker exec -it <pg-container> psql -U memory -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname='vector';"` 返回版本号
- [ ] `pytest tests/ -q` 收集 0 个测试但退出码 0
- [ ] PR 描述含：LLM 调用次数（= 0）、变更文件数声明、超预算豁免说明
- [ ] PROGRESS.md 追加 T-001 完成条目（CLAUDE.md §2.8）

---

## 6. 风险

| 风险 | 应对 |
|:---|:---|
| Windows / WSL 行尾问题 | `.gitattributes` 强制 LF；`git config core.autocrlf input` 已在 WSL 端设妥 |
| pgvector 镜像 tag 漂移 | 锁 `pgvector/pgvector:pg16`（不用 latest） |
| 21 包版本冲突 | uv 解依赖很快，遇到冲突直接报错；本 ticket 已用过的版本组合（FastAPI 0.11x + SQLAlchemy 2.0 + pydantic 2.5）已知兼容 |
| C 盘 8.2 GB 剩余 | venv 装在 WSL distro（C 盘隐性增长 ~700 MB）；Docker 镜像在 E 盘（已迁） |

---

## 7. 建议未来（不在本 ticket）

- pre-commit 加 `validate_consistency.py` hook（→ T-003 完成后）
- GitHub Actions：lint / unit / integration 三 jobs（→ T-001 完成 + T-005 stub 之后）
- pyproject `[tool.coverage]` 段（→ 首个真业务 ticket）
- VSCode `.vscode/settings.json`（→ 可选，看你想不想固化 IDE 设置）

---

## 8. 执行后用户验证步骤（在 WSL 里）

```bash
cd ~/FeishuAI-STZ
git pull origin main
uv sync
source .venv/bin/activate           # 或 uv run <cmd>
pre-commit install
pre-commit run --all-files
docker compose up -d postgres
docker compose ps                    # 应该显示 postgres healthy
docker compose exec postgres psql -U memory -d memory \
  -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname='vector';"
pytest tests/ -q
```

任一步报错 → 立即停下，把错误输出贴回来，我修。

---

> **状态**：✅ **已完成**（2026-04-29）
> **commit 链**：[c427a26](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/c427a26) → [a69dbb1](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/a69dbb1) → [fbdfac7](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/fbdfac7) → [1f6ac1a](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/1f6ac1a) → [6f957ae](https://github.com/FeishuAI-TeamSTZ/FeishuAI-STZ/commit/6f957ae)
> **DoD 全 ✓**：71 包装齐 / pre-commit 全过 / PG 容器 healthy / pgvector 0.8.2 / pytest 0 测试 exit 0 / validate_fixtures OK
> **后续 ticket**：T-002（数据层 ORM + schema.sql）
