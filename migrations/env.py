"""Alembic 迁移环境配置。

03-SCHEMA §10.4 改动顺序铁律：
    [1] 改 docs/03-SCHEMA.md
    [2] 改 schema.sql / 新建 alembic 迁移
    [3] 改 memory_engine/models.py
    [4] 跑 scripts/validate_consistency.py
    [5] PR 描述：改了 X 字段，原因 Y

T-001 占位：仅设置 env 框架；首个真实迁移 0001_initial_schema.py 由 T-003 生成。
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config 对象 —— 提供对 .ini 中值的访问
config = context.config

# 从环境变量注入 DATABASE_URL（不写死在 .ini）
db_url = os.environ.get("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# 解析日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# T-002 完成后改为：
#   from memory_engine.models import Base
#   target_metadata = Base.metadata
target_metadata = None


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连库执行。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
