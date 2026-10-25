import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.business_support import Business
from tests.integration.test_api_processes import AUTH, APIClients
from tests.integration.test_api_processes import api_clients as api_clients

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def next_snapshot(lines: AsyncIterator[str]) -> dict[str, object]:
    async with asyncio.timeout(5):
        async for line in lines:
            if line.startswith("data: "):
                return dict(json.loads(line[6:]))
    raise AssertionError("Stream closed without a snapshot")


async def test_two_public_streams_recover_current_state_without_secrets_or_open_transaction(
    business: Business, api_clients: APIClients
) -> None:
    event = await business.create(capacity=1)
    path = f"/api/events/{event.id}/stream"
    first, second = api_clients
    async with first.stream("GET", path) as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert stream.headers["x-accel-buffering"] == "no"
        lines = stream.aiter_lines()
        initial = await next_snapshot(lines)
        assert set(initial) == {
            "id",
            "description",
            "starts_at",
            "capacity",
            "schedule_version",
            "confirmed",
            "waitlisted",
            "checked_in",
            "server_time",
        }
        assert initial["confirmed"] == 0
        async with business.engine.connect() as observer:
            assert (
                await observer.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                        "AND state='idle in transaction' AND pid<>pg_backend_pid()"
                    )
                )
                == 0
            )
        response = await second.post(
            f"/api/events/{event.id}/registrations", json={"email": "live@example.test"}
        )
        assert response.status_code == 202
        assert (await next_snapshot(lines))["confirmed"] == 1
        # A second client gets a complete snapshot, without an event replay cursor.
        async with second.stream("GET", path) as other:
            assert (await next_snapshot(other.aiter_lines()))["confirmed"] == 1
    await business.join(event.id, "waiting@example.test")
    async with first.stream("GET", path) as reopened:
        assert (await next_snapshot(reopened.aiter_lines()))["waitlisted"] == 1


async def test_live_missing_event_and_shared_organizer_key(api_clients: APIClients) -> None:
    client: AsyncClient = api_clients[0]
    assert (await client.get(f"/api/events/{uuid4()}/stream")).status_code == 404
    assert (await client.get("/api/organizer/access")).status_code == 401
    assert (
        await client.get("/api/organizer/access", headers={"Authorization": "Bearer wrong"})
    ).status_code == 401
    response = await client.get("/api/organizer/access", headers=AUTH)
    assert response.status_code == 200 and response.json() == {"status": "ok"}


async def test_sse_read_finishes_cleanup_when_client_cancel_scope_is_cancelled(
    business: Business, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from anyio import CancelScope, create_task_group
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from sqlalchemy.pool import AsyncAdaptedQueuePool

    from app.api.live import read_event
    from app.services import events
    from app.services.common import EventView, event_view

    event = await business.create()
    entered = asyncio.Event()
    result: list[EventView] = []

    async def slow_read(session: AsyncSession, identity: UUID) -> EventView:
        assert identity == event.id
        async with session.begin():
            await session.execute(text("SELECT 1"))  # A real checked-out connection.
            entered.set()
            await session.execute(text("SELECT pg_sleep(0.1)"))
            return await event_view(session, event.id)

    monkeypatch.setattr(events, "get_event", slow_read)
    scope = CancelScope()

    async def disconnected_client() -> None:
        with scope:
            result.append(await read_event(async_sessionmaker(business.engine), event.id))

    async with create_task_group() as group:
        group.start_soon(disconnected_client)
        await entered.wait()
        scope.cancel()
    assert len(result) == 1 and result[0].id == event.id
    assert isinstance(business.engine.pool, AsyncAdaptedQueuePool)
    assert business.engine.pool.checkedout() == 0
    assert "Exception terminating connection" not in caplog.text


async def test_hub_shares_reads_bounds_subscribers_and_releases_last_listener(
    business: Business,
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.live import LiveCapacityError, LiveHub

    event = await business.create()
    hub = LiveHub(async_sessionmaker(business.engine), limit=10)
    subscriptions = await asyncio.gather(*(hub.subscribe(event.id) for _ in range(10)))
    assert hub.reads == 1 and len(hub.topics) == 1 and hub.subscribers == 10
    with pytest.raises(LiveCapacityError):
        await hub.subscribe(event.id)
    for subscription in subscriptions:
        snapshot = await subscription.queue.get()
        assert snapshot is not None and snapshot.id == event.id
    # Every client gets the next shared SQL snapshot, not its own poll.
    await asyncio.gather(*(subscription.queue.get() for subscription in subscriptions))
    assert hub.reads == 2
    await asyncio.gather(*(subscription.close() for subscription in subscriptions))
    assert not hub.topics and hub.subscribers == 0
    from sqlalchemy.pool import AsyncAdaptedQueuePool

    assert isinstance(business.engine.pool, AsyncAdaptedQueuePool)
    assert business.engine.pool.checkedout() == 0
    await hub.close()


async def test_failed_producer_is_retired_before_reconnect_and_old_cleanup(
    business: Business, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    import app.live as live
    from app.services.common import EventView

    event = await business.create()
    original_read = live.read_event
    fail_next = asyncio.Event()
    failed = False

    async def read(sessions: async_sessionmaker[AsyncSession], identity: UUID) -> EventView:
        nonlocal failed
        if fail_next.is_set() and not failed:
            failed = True
            # Real PostgreSQL failure, not a synthetic cached response.
            async with sessions() as session:
                await session.execute(text("SELECT 1 / 0"))
        return await original_read(sessions, identity)

    monkeypatch.setattr(live, "read_event", read)
    hub = live.LiveHub(async_sessionmaker(business.engine))
    old = await hub.subscribe(event.id)
    reopened = None
    try:
        assert await old.queue.get() is not None
        fail_next.set()
        async with asyncio.timeout(5):
            assert await old.queue.get() is None
        await business.join(event.id, "reconnect@example.test")
        # Reconnect before the old HTTP stream's finally has run.
        reopened = await hub.subscribe(event.id)
        current = await reopened.queue.get()
        assert current is not None and current.confirmed == 1
        assert reopened.topic is not old.topic
        await old.close()
        assert hub.topics[event.id] is reopened.topic
        async with asyncio.timeout(5):
            assert await reopened.queue.get() is not None
    finally:
        await old.close()
        if reopened:
            await reopened.close()
        await hub.close()
    assert hub.subscribers == 0 and not hub.topics


async def test_initial_database_failure_allows_fresh_subscription(
    business: Business, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    import app.live as live
    from app.services.common import EventView

    event = await business.create()
    original_read = live.read_event
    first = True

    async def read(sessions: async_sessionmaker[AsyncSession], identity: UUID) -> EventView:
        nonlocal first
        if first:
            first = False
            async with sessions() as session:
                await session.execute(text("SELECT 1 / 0"))
        return await original_read(sessions, identity)

    monkeypatch.setattr(live, "read_event", read)
    hub = live.LiveHub(async_sessionmaker(business.engine))
    try:
        with pytest.raises(SQLAlchemyError):
            await hub.subscribe(event.id)
        assert not hub.topics and hub.subscribers == 0
        reopened = await hub.subscribe(event.id)
        try:
            assert await reopened.queue.get() is not None
        finally:
            await reopened.close()
    finally:
        await hub.close()


async def test_http_stream_reconnects_after_real_postgres_lock_timeout(
    business: Business, api_clients: APIClients
) -> None:
    event = await business.create()
    client = api_clients[0]
    path = f"/api/events/{event.id}/stream"
    async with client.stream("GET", path) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        assert (await next_snapshot(lines))["confirmed"] == 0
        async with business.engine.begin() as connection:
            await connection.execute(text("LOCK TABLE events IN ACCESS EXCLUSIVE MODE"))
            # Production lock_timeout ends this producer. Wait for EOF, not a delay.
            async with asyncio.timeout(8):
                async for _line in lines:
                    pass
    await business.join(event.id, "sql-recovery@example.test")
    async with client.stream("GET", path) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        assert (await next_snapshot(lines))["confirmed"] == 1
        await business.join(event.id, "sql-waiting@example.test")
        async with asyncio.timeout(5):
            while (await next_snapshot(lines))["waitlisted"] != 1:
                pass
