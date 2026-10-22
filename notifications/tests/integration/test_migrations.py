import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_migration_round_trip_and_guarded_downgrade(
    integration_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    await integration_engine.dispose()
    await asyncio.to_thread(command.downgrade, config, "base")
    async with integration_engine.connect() as connection:
        assert "notification_jobs" not in await connection.run_sync(
            lambda sync: inspect(sync).get_table_names()
        )
    await integration_engine.dispose()
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.check, config)
    identity = uuid4()
    async with integration_engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO notification_jobs (id,payload) VALUES (:id,'{}'::jsonb)"),
            {"id": identity},
        )
    try:
        await integration_engine.dispose()
        with pytest.raises(RuntimeError, match="requires empty"):
            await asyncio.to_thread(command.downgrade, config, "base")
        await integration_engine.dispose()
        async with integration_engine.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT id FROM notification_jobs WHERE id=:id"), {"id": identity}
                )
                == identity
            )
    finally:
        async with integration_engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM notification_jobs WHERE id=:id"), {"id": identity}
            )
