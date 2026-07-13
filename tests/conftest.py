"""测试共享 fixtures。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import async_session
from app.db.session import init_db
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_db():
    """确保表存在并清空 uploaded_files，避免脏数据干扰。"""
    import asyncio

    async def _setup():
        await init_db()
        async with async_session() as session:
            await session.execute(text("DELETE FROM uploaded_files"))
            await session.commit()

    asyncio.run(_setup())
    yield
