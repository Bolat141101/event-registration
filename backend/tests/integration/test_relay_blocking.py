import asyncio
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.models import EmailOutbox, Event, NotificationKind, OutboxStatus
from app.notifications.relay import Relay
from tests.integration.business_support import Business
from tests.integration.test_relay import accepted, stored
from tests.integration.test_relay import relay_settings as relay_settings

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def event_jobs(
    business: Business, count: int, per_event: int = 1
) -> list[tuple[UUID, list[EmailOutbox]]]:
    # Deterministic event scan order, with the blocked event's jobs also oldest.
    events = sorted([await business.create(per_event) for _ in range(count)], key=lambda e: e.id)
    result = []
    for event in events:
        messages = []
        for index in range(per_event):
            person = await business.join(event.id, f"job-{index}@example.test")
            messages.append(
                next(
                    message
                    for message in await business.messages(person)
                    if message.kind == NotificationKind.TICKET
                )
            )
            business.clock.now += timedelta(microseconds=1)
        result.append((event.id, messages))
    return result


@pytest.mark.parametrize("prepared", [False, True])
async def test_busy_first_event_does_not_block_second_and_recovers(
    business: Business, relay_settings: Settings, prepared: bool
) -> None:
    (first, [a]), (_, [b]) = await event_jobs(business, 2)
    delivered: list[UUID] = []

    def receive(request: httpx.Request) -> httpx.Response:
        delivered.append(UUID(json.loads(request.content)["message_id"]))
        return accepted(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        if prepared:
            assert await relay.prepare(a.id)
            business.clock.now += timedelta(seconds=1)
        before = await stored(business, a.id)
        async with AsyncSession(business.engine) as blocker, blocker.begin():
            await blocker.execute(select(Event.id).where(Event.id == first).with_for_update())
            with patch.object(relay, "prepare", wraps=relay.prepare) as prepare:
                assert await asyncio.wait_for(relay.run_once(), timeout=1)
                assert [call.args[0] for call in prepare.await_args_list] == [a.id, b.id]
            assert delivered == [b.id]
            after = await stored(business, a.id)
            assert (
                after.payload,
                after.prepared_at,
                after.attempts,
                after.available_at,
                after.last_error,
            ) == (
                before.payload,
                before.prepared_at,
                before.attempts,
                before.available_at,
                before.last_error,
            )
            assert after.status == OutboxStatus.PENDING
            assert not await asyncio.wait_for(relay.run_once(), timeout=1)
        assert await relay.run_once()
        assert delivered == [b.id, a.id]
        after = await stored(business, a.id)
        assert after.status == OutboxStatus.FORWARDED
        assert after.attempts == before.attempts + 1
        if prepared:
            assert after.payload == before.payload and after.prepared_at == before.prepared_at


async def test_one_head_per_event_preserves_order_and_does_not_fill_candidate_window(
    business: Business, relay_settings: Settings
) -> None:
    (first, a), (_, b) = await event_jobs(business, 2, per_event=3)
    limited = relay_settings.model_copy(update={"relay_candidate_limit": 2})
    delivered: list[UUID] = []

    def receive(request: httpx.Request) -> httpx.Response:
        delivered.append(UUID(json.loads(request.content)["message_id"]))
        return accepted(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            limited,
            business.clock,
        )
        async with AsyncSession(business.engine) as blocker, blocker.begin():
            await blocker.execute(select(Event.id).where(Event.id == first).with_for_update())
            for _ in b:
                assert await asyncio.wait_for(relay.run_once(), timeout=1)
            assert delivered == [message.id for message in b]
            assert not await relay.run_once()  # All remaining heads busy: worker must sleep.
            for message in a:
                untouched = await stored(business, message.id)
                assert untouched.attempts == 0 and untouched.prepared_at is None
        for _ in a:
            assert await relay.run_once()
        assert delivered == [message.id for message in [*b, *a]]
        assert not await relay.run_once()


async def test_bounded_cursor_reaches_beyond_busy_prefix_and_revisits_skipped_events(
    business: Business, relay_settings: Settings
) -> None:
    jobs = await event_jobs(business, 5)
    limited = relay_settings.model_copy(update={"relay_candidate_limit": 2})
    delivered: list[UUID] = []

    def receive(request: httpx.Request) -> httpx.Response:
        delivered.append(UUID(json.loads(request.content)["message_id"]))
        return accepted(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            limited,
            business.clock,
        )
        async with AsyncSession(business.engine) as blocker, blocker.begin():
            await blocker.execute(
                select(Event.id)
                .where(Event.id.in_([event for event, _ in jobs[:4]]))
                .order_by(Event.id)
                .with_for_update()
            )
            with patch.object(relay, "prepare", wraps=relay.prepare) as prepare:
                for _ in range(2):
                    prepare.reset_mock()
                    assert not await asyncio.wait_for(relay.run_once(), timeout=1)
                    assert prepare.await_count == 2
                assert await relay.run_once()
            assert delivered == [jobs[4][1][0].id]
        for _ in range(4):
            assert await relay.run_once()
        assert delivered == [jobs[index][1][0].id for index in [4, 0, 1, 2, 3]]


async def test_real_postgres_lock_timeout_rolls_back_prepare_before_next_event(
    business: Business, relay_settings: Settings
) -> None:
    (first, [a]), (_, [b]) = await event_jobs(business, 2)
    engine = create_async_engine(
        business.engine.url,
        isolation_level="READ COMMITTED",
        hide_parameters=True,
        connect_args={"server_settings": {"lock_timeout": "50ms"}},
    )
    delivered: list[UUID] = []

    def receive(request: httpx.Request) -> httpx.Response:
        delivered.append(UUID(json.loads(request.content)["message_id"]))
        return accepted(request)

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
            relay = Relay(
                async_sessionmaker(engine, expire_on_commit=False),
                client,
                relay_settings,
                business.clock,
            )
            async with AsyncSession(business.engine) as blocker, blocker.begin():
                # Simulate an independent administrative row lock: event NOWAIT
                # succeeds, then prepare's UPDATE actually times out at commit.
                await blocker.execute(
                    select(EmailOutbox.id).where(EmailOutbox.id == a.id).with_for_update()
                )
                with pytest.raises(DBAPIError) as error:
                    await relay.prepare(a.id)
                assert getattr(error.value.orig, "sqlstate", None) == "55P03"
                assert "lock timeout" in str(error.value.orig)
                assert await relay.run_once()
                assert delivered == [b.id]
                after = await stored(business, a.id)
                assert (
                    after.attempts == 0 and after.prepared_at is None and after.payload == a.payload
                )
                # The timed-out transaction released its event lock too.
                async with business.engine.begin() as observer:
                    assert (
                        await observer.scalar(
                            select(Event.id).where(Event.id == first).with_for_update(nowait=True)
                        )
                        == first
                    )
            assert await relay.run_once()
            assert delivered == [b.id, a.id]
    finally:
        await engine.dispose()


async def test_free_events_are_round_robin_and_unknown_db_errors_are_not_hidden(
    business: Business, relay_settings: Settings
) -> None:
    (_, a), (_, b) = await event_jobs(business, 2, per_event=2)
    delivered: list[UUID] = []

    def receive(request: httpx.Request) -> httpx.Response:
        delivered.append(UUID(json.loads(request.content)["message_id"]))
        return accepted(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        async with business.engine.connect() as connection:
            with pytest.raises(DBAPIError) as error:
                await connection.execute(text("SELECT 1 / 0"))
        with patch.object(relay, "prepare", side_effect=error.value), pytest.raises(DBAPIError):
            await relay.run_once()
        # Failed scanning advances a hint, not the durable jobs. A new relay also
        # restarts its sweep and rediscovers every still-pending message.
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        for _ in range(4):
            assert await relay.run_once()
        assert delivered == [a[0].id, b[0].id, a[1].id, b[1].id]


async def test_new_ready_event_does_not_extend_current_sweep_and_is_not_lost(
    business: Business, relay_settings: Settings
) -> None:
    events = sorted([await business.create() for _ in range(3)], key=lambda item: item.id)
    await business.join(events[0].id, "old-a@example.test")
    await business.join(events[2].id, "old-c@example.test")
    delivered: list[UUID] = []

    def receive(request: httpx.Request) -> httpx.Response:
        delivered.append(UUID(json.loads(request.content)["payload"]["event_id"]))
        return accepted(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        assert await relay.run_once()
        business.clock.now += timedelta(seconds=1)
        # This ID falls between A/C, but became due AFTER the current sweep began.
        await business.join(events[1].id, "new-b@example.test")
        assert await relay.run_once()
        assert delivered == [events[0].id, events[2].id]
        assert await relay.run_once()
        assert delivered == [events[0].id, events[2].id, events[1].id]


async def test_idle_relay_rediscovers_newly_due_jobs(
    business: Business, relay_settings: Settings
) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(accepted)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        assert not await relay.run_once()
        business.clock.now += timedelta(seconds=1)
        [(_, [message])] = await event_jobs(business, 1)
        assert await relay.run_once()
        assert (await stored(business, message.id)).status == OutboxStatus.FORWARDED
