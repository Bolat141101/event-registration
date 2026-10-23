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
