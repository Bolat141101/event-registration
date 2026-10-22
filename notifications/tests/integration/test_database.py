from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from notifications_app.health import database_is_ready, expected_schema_heads
from notifications_app.models import JobStatus, NotificationJob

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_real_database_and_schema(integration_engine: AsyncEngine) -> None:
    assert await database_is_ready(integration_engine, expected_schema_heads())
    async with integration_engine.connect() as connection:
        assert await connection.scalar(text("SHOW transaction_isolation")) == "read committed"
        tables = (
            await connection.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
        ).all()
        assert set(tables) == {"alembic_version", "notification_jobs"}
        assert (
            await connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='notification_jobs'"
                )
            )
            == 7
        )


async def test_payload_and_future_mime_round_trip(db_session: AsyncSession) -> None:
    job = NotificationJob(id=uuid4(), payload={"kind": "ticket", "recipient": "user@example.test"})
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    assert job.status == JobStatus.PENDING and job.attempts == 0
    assert job.mime is None and job.last_error is None
    assert job.available_at.utcoffset() == timedelta(0)
    job.mime = b"Message-ID: <fixed@example.test>\r\n\r\nBody\r\n"
    await db_session.flush()
    await db_session.refresh(job)
    assert job.mime == b"Message-ID: <fixed@example.test>\r\n\r\nBody\r\n"
    assert job.payload == {"kind": "ticket", "recipient": "user@example.test"}


@pytest.mark.parametrize(
    "changes,constraint",
    [
        ({"attempts": -1}, "nonnegative_attempts"),
        ({"payload": []}, "object_payload"),
        ({"mime": b""}, "nonempty_mime"),
        ({"status": JobStatus.SENT}, "sent_requires_mime"),
    ],
)
async def test_database_rejects_invalid_storage(
    db_session: AsyncSession, changes: dict[str, Any], constraint: str
) -> None:
    db_session.add(NotificationJob(**{"id": uuid4(), "payload": {}, **changes}))
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


async def test_external_job_identity_is_unique(db_session: AsyncSession) -> None:
    identity = uuid4()
    db_session.add(NotificationJob(id=identity, payload={"kind": "ticket"}))
    await db_session.flush()
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("INSERT INTO notification_jobs (id,payload) VALUES (:id,'{}'::jsonb)"),
            {"id": identity},
        )


async def test_job_write_rolls_back_with_transaction(db_session: AsyncSession) -> None:
    identity = uuid4()
    with pytest.raises(RuntimeError, match="abort"):
        async with db_session.begin_nested():
            db_session.add(NotificationJob(id=identity, payload={}))
            await db_session.flush()
            raise RuntimeError("abort")
    assert (
        await db_session.scalar(select(NotificationJob.id).where(NotificationJob.id == identity))
        is None
    )
