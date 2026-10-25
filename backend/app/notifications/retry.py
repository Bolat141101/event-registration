"""Explicit retry: preserve the ID/frozen payload and revalidate business state in relay.prepare."""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clock import Clock, utc_now
from app.config import Settings
from app.db.models import EmailOutbox, OutboxStatus
from app.db.session import build_engine, build_session_factory
from app.notifications.singleton import singleton


async def retry_failed(
    sessions: async_sessionmaker[AsyncSession], identity: UUID, clock: Clock = utc_now
) -> bool:
    async with singleton(sessions) as acquired:
        if not acquired:
            return False
        async with sessions() as session, session.begin():
            message = await session.get(EmailOutbox, identity, with_for_update=True)
            if message is None or message.status != OutboxStatus.FAILED:
                return False
            message.status = OutboxStatus.PENDING
            message.attempts = 0
            message.available_at = clock()
    return True


async def main(identity: UUID) -> None:
    engine = build_engine(Settings())
    try:
        if not await retry_failed(build_session_factory(engine), identity):
            raise SystemExit("Relay busy, job missing or not failed; no retry scheduled")
        print("One failed job scheduled with unchanged ID/payload; relay will revalidate it")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity", type=UUID)
    parser.add_argument("--acknowledge-duplicate-risk", action="store_true", required=True)
    asyncio.run(main(parser.parse_args().identity))
