"""A database-wide sender/relay mutex, independent of business transactions.

One reserved AUTOCOMMIT connection owns a session advisory lock across network I/O.
It is never returned to the pool while locked. No leases or schema are needed.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from anyio import CancelScope
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def singleton(sessions: async_sessionmaker[AsyncSession]) -> AsyncIterator[bool]:
    async with sessions() as session:
        connection = await session.connection(execution_options={"isolation_level": "AUTOCOMMIT"})
        acquired = bool(await connection.scalar(text("SELECT pg_try_advisory_lock(794632801)")))

        owner = asyncio.current_task()

        async def verify_owner() -> None:
            try:
                while True:
                    await asyncio.sleep(0.5)
                    await connection.execute(text("SELECT 1"))
            except (SQLAlchemyError, OSError):
                logger.warning("Queue ownership connection lost; cancelling current attempt")
                assert owner is not None
                owner.cancel()

        watcher = asyncio.create_task(verify_owner()) if acquired else None
        try:
            yield acquired
        finally:
            with CancelScope(shield=True):
                if watcher:
                    watcher.cancel()
                    with suppress(asyncio.CancelledError):
                        await watcher
            if acquired:
                # Never put a locked or half-closed connection back into the pool.
                with CancelScope(shield=True):
                    try:
                        await connection.execute(text("SELECT pg_advisory_unlock(794632801)"))
                    except (SQLAlchemyError, OSError):
                        await connection.invalidate()
