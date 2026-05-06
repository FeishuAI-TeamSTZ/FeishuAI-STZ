#!/usr/bin/env python3
"""schema.sql ↔ memory_engine/models.py 漂移检查（CLAUDE.md §2.4 第 4 步）。

检查项（03-SCHEMA 附录 A 规约）：
1. 表名 1:1（CREATE TABLE ↔ Base.metadata.tables）
2. 每张表的字段名 1:1（schema.sql 字段行 ↔ ORM Column 名）
3. 6 enum 的取值集合 1:1（CREATE TYPE ENUM ↔ Python enum.Enum）
4. 命名 CHECK 约束 1:1（CONSTRAINT chk_xxx ↔ ORM CheckConstraint.name）
5. 命名索引 1:1（CREATE INDEX idx_xxx ↔ ORM Index.name）
6. FK 引用关系 1:1（REFERENCES table(col) ↔ ORM ForeignKey）

退出码：
- 0 = 一致
- 1 = 漂移；stderr 列出每个不一致项

用法：
    uv run python scripts/validate_consistency.py
    # 或在 pre-commit 中作为 local hook 调用
"""

from __future__ import annotations

import re
import sys
from enum import Enum
from pathlib import Path
from typing import Any

# 触发 ORM 注册（必须在 metadata 引用前 import）
from memory_engine import models
from memory_engine.models import Base

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT / "schema.sql"

# Python enum class 与 SQL enum type 的命名映射（D14：单一真相在 schema.sql）
ENUM_PY_TO_SQL: dict[str, type[Enum]] = {
    "provenance_enum": models.Provenance,
    "evolution_type_enum": models.EvolutionType,
    "decision_state_enum": models.DecisionState,
    "card_type_enum": models.CardType,
    "card_status_enum": models.CardStatus,
    "card_response_enum": models.CardResponse,
}

# schema.sql 行内非字段的关键字（用于跳过 CONSTRAINT / PRIMARY KEY 等行）
NON_FIELD_PREFIX = re.compile(
    r"^(CONSTRAINT|PRIMARY\s+KEY|UNIQUE|CHECK|FOREIGN\s+KEY|--)", re.IGNORECASE
)

# 字段行：要求 `<name> <SQL_TYPE>` 模式；过滤多行 CHECK 内的 `AND foo IS NOT NULL` 误判
SQL_TYPE_KEYWORD = (
    r"uuid|varchar|int|smallint|bigint|text|numeric|boolean|bool|jsonb|json|"
    r"timestamptz|timestamp|date|time|vector|inet|serial|bytea|"
    r"provenance_enum|evolution_type_enum|decision_state_enum|"
    r"card_type_enum|card_status_enum|card_response_enum"
)
FIELD_LINE = re.compile(
    rf"^(\w+)\s+(?:{SQL_TYPE_KEYWORD})\b",
    re.IGNORECASE,
)

# SQL 端独有的索引白名单（pgvector HNSW + GIN tsvector 在 SQLAlchemy ORM
# 表达不优雅，由 schema.sql 单方面声明；T-004 §3 D21 95% 覆盖 + 兜底策略）
SQL_ONLY_INDEX_ALLOWLIST: frozenset[str] = frozenset(
    {
        "idx_emb_hnsw",  # HNSW pgvector
        "idx_decisions_fts",  # GIN tsvector 全文索引
    }
)


# ============================================================
# §1. schema.sql 解析
# ============================================================


def parse_schema_sql_text() -> str:
    """读取 schema.sql 全文。"""
    return SCHEMA_SQL.read_text(encoding="utf-8")


def parse_schema_tables(text: str) -> dict[str, dict[str, Any]]:
    """解析 CREATE TABLE 块 → {table: {fields, named_checks, fks}}。

    注：DEFAULT / CHECK 表达式只看名，不比较语义（D21 80% 覆盖）。
    """
    tables: dict[str, dict[str, Any]] = {}
    # CREATE TABLE <name> ( ...body... );  非贪婪 + DOTALL
    for m in re.finditer(r"CREATE TABLE (\w+)\s*\((.*?)\n\);", text, re.DOTALL):
        name = m.group(1)
        body = m.group(2)
        fields: set[str] = set()
        for raw_line in body.split("\n"):
            line = raw_line.strip().rstrip(",")
            if not line or NON_FIELD_PREFIX.match(line):
                continue
            field_m = FIELD_LINE.match(line)
            if field_m:
                fields.add(field_m.group(1))
        named_checks = set(re.findall(r"CONSTRAINT\s+(\w+)\s+CHECK", body, re.IGNORECASE))
        fks: set[tuple[str, str]] = set()
        for fk_m in re.finditer(r"REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)", body, re.IGNORECASE):
            fks.add((fk_m.group(1), fk_m.group(2)))
        tables[name] = {"fields": fields, "named_checks": named_checks, "fks": fks}
    return tables


def parse_schema_enums(text: str) -> dict[str, set[str]]:
    """解析 CREATE TYPE ... AS ENUM → {enum_name: {values}}。"""
    enums: dict[str, set[str]] = {}
    for m in re.finditer(r"CREATE TYPE (\w+) AS ENUM\s*\((.*?)\);", text, re.DOTALL):
        name = m.group(1)
        body = m.group(2)
        values = set(re.findall(r"'([\w_-]+)'", body))
        enums[name] = values
    return enums


def parse_schema_indexes(text: str) -> set[str]:
    """解析 CREATE INDEX → {index_name}。包括 UNIQUE 与 USING 形式。"""
    return set(re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+", text, re.IGNORECASE))


# ============================================================
# §2. ORM 反射
# ============================================================


def parse_orm_tables() -> dict[str, dict[str, Any]]:
    """introspect Base.metadata → 同维度 dict。"""
    tables: dict[str, dict[str, Any]] = {}
    for table in Base.metadata.tables.values():
        fields = {c.name for c in table.columns}
        named_checks = {
            ck.name
            for ck in table.constraints
            if ck.__class__.__name__ == "CheckConstraint" and ck.name
        }
        fks: set[tuple[str, str]] = set()
        for col in table.columns:
            for fk in col.foreign_keys:
                fks.add((fk.column.table.name, fk.column.name))
        tables[table.name] = {"fields": fields, "named_checks": named_checks, "fks": fks}
    return tables


def parse_orm_enums() -> dict[str, set[str]]:
    """从 ENUM_PY_TO_SQL 表反射 Python enum 取值。"""
    return {sql_name: {e.value for e in py_cls} for sql_name, py_cls in ENUM_PY_TO_SQL.items()}


def parse_orm_indexes() -> set[str]:
    """introspect 每张表的 indexes（不含 PK auto-index）。"""
    indexes: set[str] = set()
    for table in Base.metadata.tables.values():
        for idx in table.indexes:
            if idx.name:
                indexes.add(idx.name)
    return indexes


# ============================================================
# §3. 比对
# ============================================================


def diff_sets(left: set[Any], right: set[Any], left_label: str, right_label: str) -> list[str]:
    """对称差报告：左独有 / 右独有。"""
    out: list[str] = []
    only_left = left - right
    only_right = right - left
    for item in sorted(only_left, key=str):
        out.append(f"  - 只在 {left_label}: {item}")
    for item in sorted(only_right, key=str):
        out.append(f"  - 只在 {right_label}: {item}")
    return out


def diff_tables(sql_t: dict[str, dict[str, Any]], orm_t: dict[str, dict[str, Any]]) -> list[str]:
    """逐表逐字段比对。

    named_checks 单向比对（schema → ORM）：schema.sql 命名 CHECK 必须在 ORM 出现；
    反之 ORM 可有更多命名 CHECK（schema.sql 用匿名 inline CHECK 时 ORM 给显式名）。
    """
    drifts: list[str] = []
    table_drifts = diff_sets(set(sql_t), set(orm_t), "schema.sql", "ORM")
    if table_drifts:
        drifts.append("[表名漂移]")
        drifts.extend(table_drifts)
    common = set(sql_t) & set(orm_t)
    for name in sorted(common):
        sql_meta = sql_t[name]
        orm_meta = orm_t[name]
        # fields / fks: 双向严格比对
        for key in ("fields", "fks"):
            d = diff_sets(sql_meta[key], orm_meta[key], f"schema.{name}.{key}", f"ORM.{name}.{key}")
            if d:
                drifts.append(f"[{name}.{key} 漂移]")
                drifts.extend(d)
        # named_checks: 单向（schema → ORM 必须存在；ORM 可以多）
        only_in_schema = sql_meta["named_checks"] - orm_meta["named_checks"]
        if only_in_schema:
            drifts.append(f"[{name}.named_checks 漂移：schema.sql 命名 CHECK 在 ORM 缺失]")
            for c in sorted(only_in_schema):
                drifts.append(
                    f"  - schema.{name} 有 CONSTRAINT {c}，ORM 无对应 CheckConstraint(name=...)"
                )
    return drifts


def diff_enums(sql_e: dict[str, set[str]], orm_e: dict[str, set[str]]) -> list[str]:
    """逐 enum 比对取值集合。"""
    drifts: list[str] = []
    name_drifts = diff_sets(set(sql_e), set(orm_e), "schema.sql.enums", "ORM.enums")
    if name_drifts:
        drifts.append("[enum 类型名漂移]")
        drifts.extend(name_drifts)
    common = set(sql_e) & set(orm_e)
    for name in sorted(common):
        d = diff_sets(sql_e[name], orm_e[name], f"schema.{name}", f"ORM.{name}")
        if d:
            drifts.append(f"[{name} 取值漂移]")
            drifts.extend(d)
    return drifts


def diff_indexes(sql_i: set[str], orm_i: set[str]) -> list[str]:
    """命名索引集合比对。

    schema.sql 独有索引允许列表（SQL_ONLY_INDEX_ALLOWLIST）：pgvector HNSW + GIN
    tsvector 在 SQLAlchemy ORM 表达不优雅，schema.sql 单方面声明（T-004 D21 兜底）。
    """
    sql_filtered = sql_i - SQL_ONLY_INDEX_ALLOWLIST
    d = diff_sets(sql_filtered, orm_i, "schema.sql.indexes", "ORM.indexes")
    return ["[索引漂移]"] + d if d else []


# ============================================================
# §4. 主入口
# ============================================================


def check() -> list[str]:
    """运行全部漂移检查；返回漂移列表（空 = 一致）。

    供集成测 import 调用，避免 subprocess 依赖。
    """
    text = parse_schema_sql_text()
    drifts: list[str] = []
    drifts += diff_tables(parse_schema_tables(text), parse_orm_tables())
    drifts += diff_enums(parse_schema_enums(text), parse_orm_enums())
    drifts += diff_indexes(parse_schema_indexes(text), parse_orm_indexes())
    return drifts


def main() -> int:
    drifts = check()
    if drifts:
        print("schema.sql ↔ memory_engine/models.py 漂移：", file=sys.stderr)
        for line in drifts:
            print(line, file=sys.stderr)
        print(
            f"\n总计 {sum(1 for d in drifts if d.startswith('  -'))} 处漂移。" f"修复后再 commit。",
            file=sys.stderr,
        )
        return 1
    print("OK: schema.sql ↔ memory_engine/models.py 一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
