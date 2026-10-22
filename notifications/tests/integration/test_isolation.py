import os

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_application_roles_are_not_administrators(integration_engine: AsyncEngine) -> None:
    urls = [integration_engine.url, make_url(os.environ["TEST_CORE_DATABASE_URL"])]
    for url in urls:
        engine = create_async_engine(url, hide_parameters=True)
        try:
            async with engine.connect() as connection:
                flags = (
                    await connection.execute(
                        text(
                            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                            "FROM pg_roles WHERE rolname=current_user"
                        )
                    )
                ).one()
                assert tuple(flags) == (False, False, False, False, False)
                assert await connection.scalar(text("SELECT current_database()")) == url.database
        finally:
            await engine.dispose()


async def test_roles_cannot_connect_to_each_others_database(
    integration_engine: AsyncEngine,
) -> None:
    notifications = integration_engine.url
    core = make_url(os.environ["TEST_CORE_DATABASE_URL"])
    for own, other in ((notifications, core), (core, notifications)):
        engine = create_async_engine(own.set(database=other.database), hide_parameters=True)
        try:
            with pytest.raises((SQLAlchemyError, asyncpg.InsufficientPrivilegeError)) as error:
                async with engine.connect():
                    pytest.fail("Cross-database connection must be denied")
            original = getattr(error.value, "orig", error.value)
            assert getattr(original, "sqlstate", None) == "42501"
        finally:
            await engine.dispose()
