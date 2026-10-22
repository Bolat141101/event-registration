import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:test@127.0.0.1:1/event_registration_test",
        organizer_token="test_organizer_token_at_least_32_characters",
    )


@pytest.fixture
async def integration_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    url = make_url(database_url)
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("Integration tests require a dedicated database whose name ends in _test")
    if url.get_backend_name() != "postgresql":
        pytest.fail("Integration tests must run against PostgreSQL")
    if url.drivername != "postgresql+asyncpg":
        pytest.fail("Integration tests require the asyncpg driver")
    engine = create_async_engine(url, isolation_level="READ COMMITTED", hide_parameters=True)
    try:
        async with engine.connect() as connection:
            role = (
                await connection.execute(
                    text(
                        "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, "
                        "rolreplication, rolbypassrls, "
                        "EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid) "
                        "AS has_membership FROM pg_roles r WHERE rolname = current_user"
                    )
                )
            ).one()
            if role.rolname != "core_app_test" or any(role[1:]):
                pytest.fail("Core integration tests require unprivileged core_app_test")
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


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
