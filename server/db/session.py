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


async def init_db():
    """创建所有表并安全补充缺失字段。"""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
        await conn.execute(text("PRAGMA busy_timeout=5000;"))
        await conn.run_sync(Base.metadata.create_all)
        # 兼容性迁移：检查并添加 media_parse_records.file_id 字段
        try:
            await conn.execute(text("ALTER TABLE media_parse_records ADD COLUMN file_id VARCHAR(64)"))
        except Exception:
            pass  # 字段已存在
    logger.info("数据库初始化完成: %s", DATABASE_URL)


async def get_db_session() -> AsyncSession:
    """获取数据库会话。"""
    async with async_session() as session:
        yield session
