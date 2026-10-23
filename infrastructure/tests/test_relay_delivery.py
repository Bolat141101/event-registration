import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from notifications_app.config import Settings as InboxSettings
from notifications_app.main import create_app
from notifications_app.models import NotificationJob
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from test_bootstrap import anyio_backend as anyio_backend
from test_bootstrap import databases as databases

from app.config import Settings as CoreSettings
from app.db.models import EmailOutbox, Event, OutboxStatus, Registration
from app.notifications.relay import Relay
from app.services import events, registrations

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
TOKEN = "test_notifications_internal_token_32_characters_minimum"


async def test_two_databases_lost_http_response_then_both_components_restart(
    databases: tuple[AsyncEngine, AsyncEngine],
) -> None:
    core, inbox = databases
    now = datetime(2030, 1, 1, tzinfo=UTC)
    sessions = async_sessionmaker(core, expire_on_commit=False)
    settings = CoreSettings(
        database_url=core.url.render_as_string(hide_password=False),
        organizer_token="test_organizer_token_32_characters_minimum",
        notifications_internal_token=TOKEN,
    )
    async with sessions() as session:
        event = await events.create_event(
            session, "Crash recovery", now + timedelta(days=2), 1, lambda: now
        )
    identity = None
    try:
        async with sessions() as session:
            await registrations.register(session, event.id, "restart@example.test", lambda: now)
        async with sessions() as session:
            identity = await session.scalar(
                select(EmailOutbox.id).where(EmailOutbox.kind == "ticket")
            )
        assert identity is not None
        app = create_app(
            InboxSettings(
                database_url=inbox.url.render_as_string(hide_password=False),
                notifications_internal_token=TOKEN,
            )
        )
        inner = httpx.ASGITransport(app=app)
        bodies: list[bytes] = []

        class LoseCommittedResponse(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                bodies.append(request.content)
                response = await inner.handle_async_request(request)
                assert response.status_code == 202
                await response.aclose()
                raise httpx.ReadTimeout("committed response lost", request=request)

        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=LoseCommittedResponse()) as client,
        ):
            await Relay(sessions, client, settings, lambda: now).run_once()
        async with sessions() as session:
            row = await session.get(EmailOutbox, identity)
            assert row is not None and row.status == OutboxStatus.PENDING and row.attempts == 1
            frozen = row.payload
        async with AsyncSession(inbox) as session:
            job = await session.get(NotificationJob, identity)
            assert job is not None and job.payload == frozen and job.mime is None
        # No former app/pool/client/relay state is retained across the second attempt.
        await core.dispose()
        await inbox.dispose()
        now += timedelta(seconds=1)
        restarted = create_app(
            InboxSettings(
                database_url=inbox.url.render_as_string(hide_password=False),
                notifications_internal_token=TOKEN,
            )
        )
        async with (
            restarted.router.lifespan_context(restarted),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted)) as client,
        ):
            await Relay(
                async_sessionmaker(core, expire_on_commit=False), client, settings, lambda: now
            ).run_once()
        async with sessions() as session:
            row = await session.get(EmailOutbox, identity)
            assert (
                row is not None and row.status == OutboxStatus.FORWARDED and row.payload == frozen
            )
            assert row.attempts == 2
        async with AsyncSession(inbox) as session:
            jobs = (
                await session.scalars(select(NotificationJob).where(NotificationJob.id == identity))
            ).all()
            assert len(jobs) == 1 and jobs[0].payload == json.loads(bodies[0])
            assert jobs[0].status == "pending" and jobs[0].mime is None and jobs[0].attempts == 0
    finally:
        async with core.begin() as connection:
            await connection.execute(
                delete(EmailOutbox).where(
                    EmailOutbox.registration_id.in_(
                        select(Registration.id).where(Registration.event_id == event.id)
                    )
                )
            )
            await connection.execute(delete(Registration).where(Registration.event_id == event.id))
            await connection.execute(delete(Event).where(Event.id == event.id))
        if identity is not None:
            async with inbox.begin() as connection:
                await connection.execute(
                    delete(NotificationJob).where(NotificationJob.id == identity)
                )
