"""数据库连接与配置。"""

import os
import sys
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from server.db.base import Base
import server.db.orm_models  # noqa: F401 (ensure all models are registered to Base.metadata)

logger = logging.getLogger(__name__)

DATABASE_DIR = Path(__file__).parent.parent.parent / "data" / "database"

# 测试环境使用独立数据库，避免污染生产数据（兼容 pytest 导入期与执行期）
_is_testing = bool(
    os.environ.get("PYTEST_CURRENT_TEST")
    or os.environ.get("PYTEST_VERSION")
    or os.environ.get("ONEASR_TESTING")
    or "pytest" in sys.modules
)
_db_name = "oneasr_test.db" if _is_testing else "oneasr.db"
DATABASE_URL = os.environ.get("ONEASR_DATABASE_URL", f"sqlite+aiosqlite:///{DATABASE_DIR / _db_name}")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"timeout": 30.0},
    **({"poolclass": NullPool} if _is_testing else {}),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _auto_migrate_columns(sync_conn):
    """自省比对：如果 ORM 模型中有新字段而数据库物理表中没有，全自动补齐。"""
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())
    preparer = sync_conn.dialect.identifier_preparer

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue

        db_cols = {col["name"] for col in inspector.get_columns(table_name)}

        for column in table.columns:
            if column.name not in db_cols:
                col_type = column.type.compile(sync_conn.dialect)
                col_name_quoted = preparer.quote(column.name)
                table_name_quoted = preparer.quote(table_name)

                ddl = f"ALTER TABLE {table_name_quoted} ADD COLUMN {col_name_quoted} {col_type}"
                if column.server_default is not None and getattr(column.server_default, "arg", None) is not None:
                    ddl += f" DEFAULT {column.server_default.arg}"

                try:
                    sync_conn.execute(text(ddl))
                    logger.info("数据库自适应迁移: 表 '%s' 自动补齐缺失字段 '%s' (%s)", table_name, column.name, col_type)
                except Exception as e:
                    logger.warning("数据库自适应迁移异常 (%s.%s): %s", table_name, column.name, e)


async def init_db():
    """创建所有表并全自动自省补充缺失字段。"""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
        await conn.execute(text("PRAGMA busy_timeout=5000;"))
        # 1. 创建所有不存在的新表
        await conn.run_sync(Base.metadata.create_all)
        # 2. 全表自省：自动补齐任意旧表中缺失的任意新列
        await conn.run_sync(_auto_migrate_columns)
    logger.info("数据库初始化完成: %s", DATABASE_URL)


async def get_db_session() -> AsyncSession:
    """获取数据库会话。"""
    async with async_session() as session:
        yield session
