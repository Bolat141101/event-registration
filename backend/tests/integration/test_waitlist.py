"""Verify queue allocation/storage independently of the registration service."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.models import Event, Registration, RegistrationStatus
from app.db.waitlist import next_waitlist_seq

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture
async def committed_event(integration_engine: AsyncEngine) -> AsyncIterator[UUID]:
    async with AsyncSession(integration_engine, expire_on_commit=False) as session, session.begin():
        item = Event(
            description="Проверка очереди",
            starts_at=datetime.now(UTC) + timedelta(days=2),
            capacity=1,
        )
        session.add(item)
        await session.flush()
        event_id = item.id
    try:
        yield event_id
    finally:
        async with integration_engine.begin() as connection:
            (
                await connection.execute(
                    delete(Registration).where(Registration.event_id == event_id)
                )
            )
            await connection.execute(delete(Event).where(Event.id == event_id))


async def enqueue(session: AsyncSession, event_id: UUID) -> Registration:
    position = await next_waitlist_seq(session, event_id)
    entry = Registration(
        event_id=event_id,
        email=f"{uuid4().hex}@example.test",
        status=RegistrationStatus.WAITLISTED,
        waitlist_seq=position,
        manage_token_hash=uuid4().hex,
    )
    session.add(entry)
    await session.flush()
    return entry


async def test_allocation_requires_caller_transaction(integration_engine: AsyncEngine) -> None:
    async with AsyncSession(integration_engine, expire_on_commit=False) as session:
        with pytest.raises(RuntimeError, match="explicit caller transaction"):
            await next_waitlist_seq(session, uuid4())


async def test_allocation_rejects_unknown_event(integration_engine: AsyncEngine) -> None:
    async with AsyncSession(integration_engine, expire_on_commit=False) as session, session.begin():
        with pytest.raises(LookupError, match="does not exist"):
            await next_waitlist_seq(session, uuid4())


async def test_fifo_tail_reuse_after_cancel_and_promotion(
    integration_engine: AsyncEngine, committed_event: UUID
) -> None:
    async with AsyncSession(integration_engine, expire_on_commit=False) as session, session.begin():
        first = await enqueue(session, committed_event)
        second = await enqueue(session, committed_event)
        third = await enqueue(session, committed_event)
        assert [first.waitlist_seq, second.waitlist_seq, third.waitlist_seq] == [1, 2, 3]
        # Storage transitions only; automatic promotion is covered by business tests.
        third.status = RegistrationStatus.CANCELLED
        third.waitlist_seq = None
        await session.flush()
        replacement = await enqueue(session, committed_event)
        assert replacement.waitlist_seq == 3
        ordered = (
            await session.scalars(
                select(Registration)
                .where(
                    Registration.event_id == committed_event,
                    Registration.status == RegistrationStatus.WAITLISTED,
                )
                .order_by(Registration.waitlist_seq)
            )
        ).all()
        assert [entry.id for entry in ordered] == [first.id, second.id, replacement.id]
        first.status = RegistrationStatus.CONFIRMED
        first.ticket_code = uuid4().hex
        first.waitlist_seq = None
        await session.flush()
        assert (await next_waitlist_seq(session, committed_event)) == 4
        for entry in (second, replacement):
            entry.status = RegistrationStatus.CANCELLED
            entry.waitlist_seq = None
        await session.flush()
        assert (await next_waitlist_seq(session, committed_event)) == 1


async def test_rollback_does_not_reserve_queue_position(
    integration_engine: AsyncEngine, committed_event: UUID
) -> None:
    async with AsyncSession(integration_engine, expire_on_commit=False) as session:
        with pytest.raises(RuntimeError, match="abort"):
            async with session.begin():
                assert (await enqueue(session, committed_event)).waitlist_seq == 1
                raise RuntimeError("abort")
        async with session.begin():
            assert (await enqueue(session, committed_event)).waitlist_seq == 1


async def test_concurrent_allocation_waits_for_event_lock_and_reads_committed_max(
    integration_engine: AsyncEngine, committed_event: UUID
) -> None:
    second_started = asyncio.Event()
    second_pid: list[int] = []

    async def second_transaction() -> int | None:
        async with AsyncSession(integration_engine) as session, session.begin():
            second_pid.append((await session.execute(text("SELECT pg_backend_pid()"))).scalar_one())
            second_started.set()
            return (await enqueue(session, committed_event)).waitlist_seq

    # Separate asyncio tasks/connections/transactions; no shared session or mock lock.
    async with (
        asyncio.TaskGroup() as group,
        AsyncSession(integration_engine) as first,
        first.begin(),
    ):
        assert (await enqueue(first, committed_event)).waitlist_seq == 1
        first_pid = (await first.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        task = group.create_task(second_transaction())
        await asyncio.wait_for(second_started.wait(), timeout=5)
        deadline = monotonic() + 5
        async with integration_engine.connect() as observer:
            while monotonic() < deadline:
                blockers = (
                    await observer.execute(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": second_pid[0]}
                    )
                ).scalar_one()
                if first_pid in blockers:
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("The second transaction did not wait for the event lock")
        assert not task.done()
    assert task.result() == 2
    async with AsyncSession(integration_engine) as session:
        positions = (
            await session.scalars(
                select(Registration.waitlist_seq)
                .where(Registration.event_id == committed_event)
                .order_by(Registration.waitlist_seq)
            )
        ).all()
        assert positions == [1, 2]
