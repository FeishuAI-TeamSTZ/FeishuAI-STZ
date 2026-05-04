# T-004：schema↔ORM 漂移检查 + alembic 包装 + 集成测

> **类型**：Phase 0 骨架 ticket（系列 4/5）
> **领地**：R1 内核工程师（`scripts/` + `migrations/` + `tests/integration/`）
> **优先级**：P0（启用 [CLAUDE.md §2.4](../CLAUDE.md) 第 4 步；解锁 T-005 utils 接入与未来字段迁移）
> **计划用时**：1 天
> **关联 §8 接口**：[03-SCHEMA 附录 A](../docs/03-SCHEMA.md)（`validate_consistency.py` 规约）；[04-ENGUIDE §10.1](../docs/04-ENGUIDE.md)（pre-commit local hook）；[04-ENGUIDE §6.1](../docs/04-ENGUIDE.md)（集成测纪律）
> **触及不变量**：无新增；持续守护 schema↔models 1:1（CLAUDE.md §2.4）
> **预算自检**：CLAUDE.md §6 ≤500 行 / ≤5 文件 → 本 ticket 5 文件 ~320 行；**预算内，无豁免**
> **依据文档**：[03-SCHEMA](../docs/03-SCHEMA.md) §0.2 / §10 / 附录 A；[04-ENGUIDE](../docs/04-ENGUIDE.md) §6.1 / §10.1；[01-CONSTITUTION §3.2](../docs/01-CONSTITUTION.md)（不引入新依赖）

---

## 1. 目标

让以下命令在 **WSL2 + 已起 PG 容器** 环境下零错误执行：

```bash
# 1) 干跑漂移检查（无漂移返 0）
uv run python scripts/validate_consistency.py

# 2) alembic 应用迁移到 fresh DB（schema.sql 由 0001 包装）
uv run alembic upgrade head

# 3) 集成测：testcontainers 起 PG → upgrade → validate → 反向 W2/W14 CHECK 触发
uv run pytest -q -m integration tests/integration/

# 4) 默认 pytest 不收集集成测（保持开发期 < 5s）
uv run pytest -q   # 只跑 tests/unit/，仍 73 passed

# 5) pre-commit 含 validate_consistency hook（commit 时自动跑，无漂移则过）
uv run pre-commit run --all-files
```

完成后，**schema.sql 与 models.py 的字段级漂移会被本地 hook + CI 双层拦截**，T-005 / T-006 后续的 ORM 字段改动有人盯。

---

## 2. 范围

### 2.1 In Scope（5 文件，~320 行）

| # | 路径 | 估算 | 说明 |
|:---:|:---|:---:|:---|
| 1 | `scripts/validate_consistency.py` | ~200 | 解析 schema.sql（正则）+ introspect `Base.metadata` → 比对 8 表 / 字段 / NN / DEFAULT / 6 enum / 索引 / FK；exit 0=一致 / 1=漂移；stdout 列差异 |
| 2 | `migrations/versions/0001_initial_schema.py` | ~40 | `op.execute(Path('schema.sql').read_text())`（D22）+ downgrade 反向 DROP 8 表 + 6 enum + EXTENSION |
| 3 | `tests/integration/test_int_schema.py` | ~80 | testcontainers `PostgresContainer("pgvector/pgvector:pg16")` → alembic upgrade head → `validate_consistency.py` exit 0 → 反向 INSERT W2 / W14 CHECK 触发；`@pytest.mark.integration` |
| 4 | `.pre-commit-config.yaml` | +10 行 | 取消注释 `validate-consistency` local hook（已预留 §41–48 行段） |
| 5 | `pyproject.toml` | +3 行 | `[tool.pytest.ini_options].addopts` 加 `-m 'not integration'`（D23） |

**附带文档微订正**：03-SCHEMA 附录 A "T-003 启用" → 改为"T-004 启用 ✓"；CLAUDE.md §2.4 第 4 步去掉 "T-003 实现后启用" 时序标注。

### 2.2 Out of Scope

| 不做 | 归属 |
|:---|:---:|
| `migrations/versions/0002_add_pgvector_ext.py`（pgvector 已经在 schema.sql 头部 `CREATE EXTENSION`，0001 包含） | 不需要 |
| 字段级 alembic 迁移（增/删/改字段的真 op） | 未来真有 schema 变更 ticket 时按需写 |
| LLM / 飞书网关 | T-005 |
| M1–M7 业务模块 | T-006+ |
| GitHub Actions CI 配置（04-ENGUIDE §10.2） | 单独 ticket（T-XXX），本 ticket 不做 |

### 2.3 预算（无豁免）

| 维度 | 上限 | 本 ticket | 状态 |
|:---|:---:|:---:|:---|
| 代码行数 | ≤ 500 | ~320 | ✓ |
| 文件数 | ≤ 5 | 5 | ✓ |
| LLM 调用 | ≤ 50 | 0 | ✓ |
| 测试时长 | ≤ 60s | 单测 < 5s；集成测首跑 ≤ 60s（含 testcontainers PG 启动） | ✓ |

---

## 3. 关键决策

### D21：SQL 解析用正则，不引入新依赖

schema.sql 结构稳定（T-002 锁定），8 表 + 6 enum + 索引 + CHECK 都在固定段落。正则可达 ~95% 覆盖；剩余 5% 边缘 case（如多行 CHECK）用 SQLAlchemy `Base.metadata` 反查兜底。**不引入** `sqlparse` 等新依赖（[宪法 §3.2](../docs/01-CONSTITUTION.md)）。

### D22：alembic 0001 = `op.execute(schema.sql)` 整文件包装

```python
def upgrade() -> None:
    sql = Path(__file__).resolve().parents[2] / "schema.sql"
    op.execute(sa.text(sql.read_text(encoding="utf-8")))
```

理由：(1) schema.sql 是**单一真相源**（CLAUDE.md §2.4）；拆成 alembic ops 等于双源，违反"先改 SCHEMA → schema.sql → models.py" 顺序；(2) 17 天周期内不会有破坏性 schema 改动，alembic 真正派上用场是 v2 字段演进。

downgrade 反向 DROP（手写）：
```python
def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS decay_calculations, reflect_logs, cards, "
               "card_quota, decision_embeddings, decisions, trace_log, users CASCADE")
    op.execute("DROP TYPE IF EXISTS card_response_enum, card_status_enum, "
               "card_type_enum, decision_state_enum, evolution_type_enum, provenance_enum")
    # 不 DROP EXTENSION vector（其他 schema 可能依赖）
```

### D23：集成测默认跳过，显式 `-m integration` 才跑

`pyproject.toml [tool.pytest.ini_options]`:
```toml
addopts = ["--strict-markers", "--strict-config", "-ra", "-m", "not integration"]
```

本机开发期 `pytest -q` 只跑 unit（~1s）；CI 或本地手工 `pytest -m integration` 跑（启动 testcontainers PG，~30–60s）。`-m integration` 与 unit 测试**不重合**（unit 测试无 marker，被 `not integration` 选中）。

### D24：`validate_consistency.py` 是脚本不是库；漂移 → exit 1 + stderr

```python
if __name__ == "__main__":
    drifts = check()
    if drifts:
        for d in drifts:
            print(d, file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
```

应用层任何地方需要"软"调用时，通过 `subprocess.run(...).returncode` 即可；不强行包成 lib。但本 ticket 一并加 `tests/unit/test_exceptions.py` 里 `DBConsistencyError` 的 instantiate 测试，让异常树覆盖率与文档保持一致（已有，无需改）。

---

## 4. 文件大纲

### 4.1 `scripts/validate_consistency.py`（~200 行）

```python
"""schema.sql ↔ memory_engine/models.py 漂移检查（CLAUDE.md §2.4 第 4 步）。"""
from __future__ import annotations
import re, sys
from pathlib import Path

import sqlalchemy as sa
from memory_engine.models import Base  # 触发 ORM 注册

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT / "schema.sql"

def parse_schema_sql() -> dict[str, dict]:
    """正则解析 schema.sql → {table: {fields, nn, defaults, checks, indexes, fks}}。"""
    text = SCHEMA_SQL.read_text(encoding="utf-8")
    tables: dict[str, dict] = {}
    # CREATE TABLE 块
    for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\);", text, re.DOTALL):
        ...
    return tables

def parse_orm() -> dict[str, dict]:
    """introspect Base.metadata → 同维度 dict。"""
    tables: dict[str, dict] = {}
    for table in Base.metadata.tables.values():
        tables[table.name] = {
            "fields": {c.name for c in table.columns},
            "nn": {c.name for c in table.columns if not c.nullable},
            "checks": {ck.name for ck in table.constraints if ck.__class__.__name__ == "CheckConstraint"},
            "indexes": {idx.name for idx in table.indexes},
        }
    return tables

def parse_schema_enums() -> dict[str, set[str]]: ...
def parse_orm_enums() -> dict[str, set[str]]: ...

def diff(sql: dict, orm: dict, label: str) -> list[str]: ...

def check() -> list[str]:
    drifts: list[str] = []
    drifts += diff(parse_schema_sql(), parse_orm(), "tables")
    drifts += diff(parse_schema_enums(), parse_orm_enums(), "enums")
    return drifts

if __name__ == "__main__":
    drifts = check()
    if drifts:
        for d in drifts:
            print(d, file=sys.stderr)
        sys.exit(1)
    print("OK: schema.sql ↔ models.py 一致")
    sys.exit(0)
```

### 4.2 `migrations/versions/0001_initial_schema.py`（~40 行）

详 D22。

### 4.3 `tests/integration/test_int_schema.py`（~80 行）

```python
"""集成测：testcontainers PG → alembic upgrade → validate → W2/W14 反向。"""
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_engine():
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        url = pg.get_connection_url().replace("postgresql://", "postgresql+psycopg://")
        # 跑 alembic upgrade head
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            env={**os.environ, "DATABASE_URL": url},
            check=True,
        )
        yield create_engine(url)


def test_validate_consistency_zero(pg_engine):
    """alembic upgrade 后 validate_consistency 必须 exit 0。"""
    result = subprocess.run(
        ["uv", "run", "python", "scripts/validate_consistency.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_w2_check_neg_supersedes_null_parent(pg_engine):
    """W2 CHECK 负样本：SUPERSEDES + parent_id NULL → CheckViolation。"""
    with pg_engine.connect() as conn, pytest.raises(Exception, match="chk_decisions_evolution_parent"):
        conn.execute(text("INSERT INTO decisions (...) VALUES (...)"))
        conn.commit()


def test_w14_check_neg_count_exceeds_max(pg_engine):
    """W14 CHECK 负样本：count > max_daily → CheckViolation。"""
    ...
```

### 4.4 `.pre-commit-config.yaml`（取消注释 §41–48 行）

```yaml
  - repo: local
    hooks:
      - id: validate-consistency
        name: schema.sql ↔ models.py 漂移检查
        entry: uv run python scripts/validate_consistency.py
        language: system
        pass_filenames: false
        always_run: true
```

### 4.5 `pyproject.toml` 修订

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "benchmark"]
...
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
    "-m", "not integration",   # T-004: 默认排除集成测
]
```

---

## 5. DoD（完成判定）

- [ ] 5 文件创建/修订，行数 ±20% 内
- [ ] `uv run python scripts/validate_consistency.py` 在当前 schema/models 上 exit 0
- [ ] `uv run alembic upgrade head` 在 fresh PG 容器上零错误
- [ ] `uv run pytest -q` 仍 **73 passed**（unit only，未拉入集成测）
- [ ] `uv run pytest -m integration tests/integration/` 全过（≥ 3 个集成测）
- [ ] `uv run pre-commit run --all-files` 全过（含新 validate-consistency hook）
- [ ] mypy --strict 在 scripts/ + tests/integration/ 上 Success（脚本与集成测同样严格）
- [ ] **故意漂移自检**：临时在 models.py 加一个不在 schema.sql 的字段 → `validate_consistency.py` exit 1 + stderr 报告该字段 → 删除字段后 exit 0
- [ ] PR 描述：LLM 调用 = 0；5 文件清单；预算未豁免；故意漂移自检截图
- [ ] PROGRESS.md 追加 Day N+ T-004 完成条目
- [ ] CLAUDE.md §2.4 + 03-SCHEMA 附录 A 更新"T-003 启用" → "T-004 启用 ✓"

---

## 6. 风险

| 风险 | 应对 |
|:---|:---|
| testcontainers 首次拉镜像慢（不复用本地 docker 镜像）| 用 `pgvector/pgvector:pg16`（与 docker-compose 同镜像，本地已有缓存）；首跑预计 ≤ 30s |
| alembic env.py 当前是 T-001 占位，可能不识别 `Base.metadata` | T-004 内顺手把 `migrations/env.py` 的 `target_metadata = None` 改为 `from memory_engine.models import Base; target_metadata = Base.metadata`；不另开 ticket |
| pre-commit 加 validate-consistency 后每次 commit 都跑（即使没改 schema/models） | `language: system + pass_filenames: false + always_run: true`；脚本 < 1s 不影响体验；如有性能问题改 `files: ^(schema\.sql\|memory_engine/models\.py)$` 触发 |
| 正则解析 schema.sql 在多行 CHECK / 复杂 INDEX 上漏 | 兜底策略：脚本先报告"已知不解析的段落"，不直接 exit 1；T-005 / T-006 真触发漂移时再加正则规则 |
| testcontainers 在 WSL 内连 Docker Desktop 偶尔握手慢 | `@pytest.fixture(scope="module")` 让 PG 容器在整个测试模块内复用，不每个测试重启 |
| 集成测 `subprocess.run(["uv", "run", ...])` 在 testcontainers 内可能找不到 uv | 用 `os.execvp` / 或直接 import `validate_consistency` module 调函数（不走子进程）—— 实施时优先后者，子进程留 alembic upgrade |

---

## 7. 建议未来（不在本 ticket）

- **T-005**：utils 层（llm_gateway / feishu_client / cache / embeddings / invariants）
- **T-006**：M1 切片（webhook → cold_path → extractor → evolution_judge → cards → decay 端到端）
- GitHub Actions CI（04-ENGUIDE §10.2）：把本 ticket 的 `validate-consistency` + `pytest -m integration` + `pytest -q unit` 拉到 CI；条件触发后单独 ticket
- 正则解析升级：当 schema.sql 增加新 SQL 构造（partial index、generated column 等）时按需扩

---

## 8. 执行后用户验证步骤

```bash
cd ~/FeishuAI-STZ
git pull origin main

# 1) 单测仍全过且不收集集成测
uv run pytest -q
# 期望：73 passed in <2s

# 2) validate_consistency 干跑
uv run python scripts/validate_consistency.py
# 期望：OK: schema.sql ↔ models.py 一致 / exit 0

# 3) alembic upgrade 在 fresh DB
docker compose down && docker compose up -d postgres
uv run alembic upgrade head
# 期望：8 表 + 6 enum + extension vector 全部就位

# 4) 集成测全过
uv run pytest -q -m integration
# 期望：≥ 3 passed in <60s

# 5) 故意漂移自检
# 在 memory_engine/models.py 临时加：fake_field: Mapped[str] = mapped_column(String)
uv run python scripts/validate_consistency.py
# 期望：exit 1 + stderr 列出 "users.fake_field 在 ORM 但不在 schema.sql"
# 删除后再跑 → exit 0

# 6) pre-commit 全过
uv run pre-commit run --all-files
```

任一步报错 → 立即停下，把错误输出贴回来，我修。

---

> **状态**：📝 草稿（2026-05-05 创建，下一会话实施）
> **后续 ticket**：T-005（utils 层：LLM 网关 + 飞书网关 + 缓存 + 嵌入 + 不变量运行时）
