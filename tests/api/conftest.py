"""API test configuration — isolates and cleans test DB tables per test."""

import asyncio
import pytest
from sqlalchemy import text

from server.db import async_session, init_db


@pytest.fixture(autouse=True)
def _clean_api_db():
    """Ensure tables exist and clean all rows before each API test."""
    async def _setup():
        await init_db()
        async with async_session() as s:
            await s.execute(text("DELETE FROM uploaded_files"))
            await s.execute(text("DELETE FROM media_parse_records"))
            await s.execute(text("DELETE FROM file_transcription_records"))
            await s.execute(text("DELETE FROM transcription_tasks"))
            await s.execute(text("DELETE FROM transcription_segments"))
            await s.execute(text("DELETE FROM streaming_records"))
            await s.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_setup())
    finally:
        loop.close()
    yield
