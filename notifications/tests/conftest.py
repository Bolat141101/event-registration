import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from notifications_app.config import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:private-password@127.0.0.1:1/notifications_test"
    )


@pytest.fixture
async def integration_engine() -> AsyncIterator[AsyncEngine]:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    url = make_url(value)
    if (
        url.drivername != "postgresql+asyncpg"
        or not url.database
        or not url.database.endswith("_test")
    ):
        pytest.fail("Notifications tests require asyncpg and a dedicated database ending in _test")
    engine = create_async_engine(url, isolation_level="READ COMMITTED", hide_parameters=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(integration_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with integration_engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        await transaction.rollback()
