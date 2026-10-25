"""Explicit operator retry of one failed job; never revive jobs through HTTP replay."""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notifications_app.clock import Clock, utc_now
from notifications_app.config import Settings
from notifications_app.contract import NotificationMessage
from notifications_app.db import build_engine, build_session_factory
from notifications_app.mime import load_prepared
from notifications_app.models import JobStatus, NotificationJob
from notifications_app.singleton import singleton


async def retry_failed(
    sessions: async_sessionmaker[AsyncSession], identity: UUID, clock: Clock = utc_now
) -> bool:
    async with singleton(sessions) as acquired:
        if not acquired:
            return False
        return await _retry_failed(sessions, identity, clock)


async def _retry_failed(
    sessions: async_sessionmaker[AsyncSession], identity: UUID, clock: Clock
) -> bool:
    async with sessions() as session, session.begin():
        job = await session.get(NotificationJob, identity, with_for_update=True)
        if job is None or job.status != JobStatus.FAILED:
            return False
        message = NotificationMessage.model_validate(job.payload)
        if message.message_id != job.id:
            raise ValueError("Invalid stored message identity")
        if job.mime is not None:
            load_prepared(message, job.mime)
        # Retain last_error for diagnostics until the next outcome. Never clear MIME.
        job.status = JobStatus.PENDING
        job.attempts = 0
        job.available_at = clock()
    return True


async def main(identity: UUID) -> None:
    engine = build_engine(Settings())
    try:
        try:
            changed = await retry_failed(build_session_factory(engine), identity)
        except ValueError:
            raise SystemExit("Invalid stored job; no retry scheduled") from None
        if not changed:
            raise SystemExit("Job is missing or not failed; no retry scheduled")
        print("One failed job scheduled with unchanged ID, payload and MIME")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stop sender before retry; SMTP may duplicate email"
    )
    parser.add_argument("identity", type=UUID)
    parser.add_argument("--acknowledge-duplicate-risk", action="store_true", required=True)
    arguments = parser.parse_args()
    asyncio.run(main(arguments.identity))
