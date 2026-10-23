"""Real HTTP races between independent API processes, engines and connection pools."""

import asyncio
import multiprocessing
import os
import socket
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from datetime import datetime, timedelta
from multiprocessing.process import BaseProcess
from uuid import UUID

import pytest
import uvicorn
from httpx import AsyncClient, Response, TransportError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import EmailOutbox, Event, NotificationKind, OutboxStatus, Registration
from app.main import create_app
from tests.integration.business_support import Business, FakeClock

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
ORGANIZER = "process_organizer_secret_at_least_32_characters"
AUTH = {"Authorization": f"Bearer {ORGANIZER}"}
type APIClients = tuple[AsyncClient, AsyncClient]


def serve_api(listener: socket.socket, database_url: str, now: datetime) -> None:
    """Each spawned child owns its app lifespan, engine and event loop."""
    app = create_app(
        Settings(database_url=database_url, organizer_token=ORGANIZER), clock=FakeClock(now)
    )
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    server.run(sockets=[listener])


async def wait_ready(client: AsyncClient, process: BaseProcess) -> None:
    async with asyncio.timeout(15):
        while True:
            assert process.is_alive(), f"API process exited: {process.exitcode}"
            try:
                response = await client.get("/api/health")
                if response.status_code == 200:
                    assert response.json() == {"status": "ok", "database": "ready"}
                    return
            except TransportError:
                pass
            await asyncio.sleep(0.02)


@pytest.fixture
async def api_clients(business: Business) -> AsyncIterator[APIClients]:
    # Spawn never inherits the parent's SQLAlchemy engine or running event loop.
    context = multiprocessing.get_context("spawn")
    processes: list[BaseProcess] = []
    try:
        async with AsyncExitStack() as stack:
            clients = []
            for index in range(2):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                    listener.bind(("127.0.0.1", 0))
                    address = f"http://127.0.0.1:{listener.getsockname()[1]}"
                    process: BaseProcess = context.Process(
                        target=serve_api,
                        args=(
                            listener,
                            os.environ["TEST_DATABASE_URL"],
                            business.clock() + timedelta(seconds=index),
                        ),
                    )
                    process.start()
                    processes.append(process)
                clients.append(
                    await stack.enter_async_context(
                        AsyncClient(base_url=address, timeout=5, trust_env=False)
                    )
                )
            assert len({process.pid for process in processes}) == 2
            assert all(
                process.pid is not None and process.pid != os.getpid() for process in processes
            )
            await asyncio.gather(
                *(
                    wait_ready(client, process)
                    for client, process in zip(clients, processes, strict=True)
                )
            )
            yield clients[0], clients[1]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        stopped_gracefully = True
        for process in processes:
            await asyncio.to_thread(process.join, 5)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join, 5)
                stopped_gracefully = False
            process.close()
        assert stopped_gracefully, "API process did not stop after SIGTERM"


async def concurrent_posts(
    business: Business,
    clients: APIClients,
    event_id: UUID,
    path: str,
    bodies: tuple[dict[str, str], dict[str, str]],
) -> list[Response]:
    async with (
        asyncio.TaskGroup() as group,
        AsyncSession(business.engine) as blocker,
        blocker.begin(),
    ):
        await blocker.execute(select(Event.id).where(Event.id == event_id).with_for_update())
        tasks = [
            group.create_task(client.post(path, json=body, headers=AUTH))
            for client, body in zip(clients, bodies, strict=True)
        ]
        async with business.engine.connect() as observer, asyncio.timeout(1.5):
            while True:
                await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                blocked = await observer.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                        "AND cardinality(pg_blocking_pids(pid)) > 0"
                    )
                )
                if blocked == 2:
                    break
                await asyncio.sleep(0.01)
            assert all(not task.done() for task in tasks)
        # Commit releases the event lock; only then do both HTTP requests complete.
    return [task.result() for task in tasks]


async def test_last_place_across_two_api_processes(
    business: Business, api_clients: APIClients
) -> None:
    event = await business.create(capacity=1)
    responses = await concurrent_posts(
        business,
        api_clients,
        event.id,
        f"/api/events/{event.id}/registrations",
        ({"email": "first@example.test"}, {"email": "second@example.test"}),
    )
    assert [response.status_code for response in responses] == [202, 202]
    assert responses[0].json() == responses[1].json()
    assert set(responses[0].json()) == {"message"}
    async with AsyncSession(business.engine) as session:
        entries = (
            await session.scalars(select(Registration).where(Registration.event_id == event.id))
        ).all()
        assert len(entries) == 2
        assert {entry.email for entry in entries} == {"first@example.test", "second@example.test"}
        assert sorted(entry.status for entry in entries) == ["confirmed", "waitlisted"]
        confirmed = next(entry for entry in entries if entry.status == "confirmed")
        waiting = next(entry for entry in entries if entry.status == "waitlisted")
        assert confirmed.ticket_code and confirmed.waitlist_seq is None
        assert waiting.ticket_code is None and waiting.waitlist_seq == 1
        messages = (
            await session.scalars(
                select(EmailOutbox).where(
                    EmailOutbox.registration_id.in_([entry.id for entry in entries])
                )
            )
        ).all()
        assert len(messages) == len({message.dedup_key for message in messages}) == 4
        assert sum(message.kind == NotificationKind.TICKET for message in messages) == 1
        assert sum(message.kind == NotificationKind.WAITLIST for message in messages) == 1
        assert sum(message.kind == NotificationKind.REMINDER for message in messages) == 2
        assert all(message.status == OutboxStatus.PENDING for message in messages)
        for entry in entries:
            assert sum(message.registration_id == entry.id for message in messages) == 2
    for client in api_clients:
        snapshot = await client.get(f"/api/events/{event.id}")
        assert snapshot.status_code == 200
        assert [snapshot.json()[key] for key in ("confirmed", "waitlisted", "checked_in")] == [
            1,
            1,
            0,
        ]


async def test_single_checkin_across_two_api_processes(
    business: Business, api_clients: APIClients
) -> None:
    # Setup is before the event; children check in at its start and one second later.
    starts_at = business.clock()
    business.clock.now -= timedelta(hours=1)
    event = await business.create(starts_at=starts_at)
    person = await business.join(event.id, "checked@example.test")
    ticket = (await business.private(person)).ticket_code
    assert ticket is not None
    before = [
        (message.id, message.payload, message.status) for message in await business.messages(person)
    ]
    path = f"/api/events/{event.id}/check-ins"
    responses = await concurrent_posts(
        business,
        api_clients,
        event.id,
        path,
        ({"ticket_code": ticket}, {"ticket_code": ticket}),
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    accepted = next(response for response in responses if response.status_code == 200)
    rejected = next(response for response in responses if response.status_code == 409)
    assert rejected.json()["code"] == "already_checked_in"
    timestamp = datetime.fromisoformat(accepted.json()["checked_in_at"])
    assert timestamp == starts_at + timedelta(seconds=responses.index(accepted))
    assert accepted.json()["id"] == str(person.id)
    async with AsyncSession(business.engine) as session:
        entries = (
            await session.scalars(select(Registration).where(Registration.event_id == event.id))
        ).all()
        assert len(entries) == 1
        assert entries[0].checked_in_at == timestamp
        assert entries[0].ticket_code == ticket and entries[0].status == "confirmed"
    for client in api_clients:
        repeat = await client.post(path, headers=AUTH, json={"ticket_code": ticket})
        assert repeat.status_code == 409 and repeat.json()["code"] == "already_checked_in"
        snapshot = await client.get(f"/api/events/{event.id}")
        assert snapshot.status_code == 200
        assert [snapshot.json()[key] for key in ("confirmed", "waitlisted", "checked_in")] == [
            1,
            0,
            1,
        ]
    assert (await business.private(person)).checked_in_at == timestamp
    assert [
        (message.id, message.payload, message.status) for message in await business.messages(person)
    ] == before
