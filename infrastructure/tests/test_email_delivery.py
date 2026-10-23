"""Business transitions -> immutable HTTP -> persisted MIME -> real test Mailpit."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from functools import partial
from uuid import UUID

import httpx
import pytest
from notifications_app.config import Settings as NotificationSettings
from notifications_app.main import create_app
from notifications_app.models import NotificationJob
from notifications_app.sender import Sender
from notifications_app.smtp import send_email
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_bootstrap import anyio_backend as anyio_backend
from test_bootstrap import databases as databases

from app.config import Settings as CoreSettings
from app.db.models import EmailOutbox, Event, Registration
from app.notifications.relay import Relay
from app.services import events, registrations
from app.services.common import EventView

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
TOKEN = "test_notifications_internal_token_32_characters_minimum"


@dataclass
class Pipeline:
    core: AsyncEngine
    inbox: AsyncEngine
    http: httpx.AsyncClient
    now: datetime = datetime(2030, 1, 1, tzinfo=UTC)
    event_ids: list[UUID] = field(default_factory=list)

    def clock(self) -> datetime:
        return self.now

    def relay(self) -> Relay:
        config = CoreSettings(
            database_url=self.core.url.render_as_string(hide_password=False),
            organizer_token="test_organizer_token_32_characters_minimum",
            notifications_internal_token=TOKEN,
        )
        return Relay(
            async_sessionmaker(self.core, expire_on_commit=False),
            self.http,
            config,
            self.clock,
        )

    def sender(self) -> Sender:
        assert os.environ["SMTP_HOST"] == "test-mailpit"
        config = NotificationSettings(
            database_url=self.inbox.url.render_as_string(hide_password=False),
            notifications_internal_token=TOKEN,
        )
        return Sender(
            async_sessionmaker(self.inbox, expire_on_commit=False),
            config,
            partial(send_email, settings=config),
            self.clock,
        )

    async def create(self, days: float = 2) -> EventView:
        async with async_sessionmaker(self.core, expire_on_commit=False)() as session:
            event = await events.create_event(
                session,
                "Email pipeline",
                self.now + timedelta(days=days),
                1,
                self.clock,
            )
        self.event_ids.append(event.id)
        return event

    async def join(self, event: EventView) -> tuple[UUID, str]:
        async with async_sessionmaker(self.core)() as session:
            await registrations.register(session, event.id, "pipeline@example.test", self.clock)
        async with async_sessionmaker(self.core)() as session:
            message = await session.scalar(
                select(EmailOutbox)
                .join(Registration)
                .where(Registration.event_id == event.id, EmailOutbox.kind == "ticket")
            )
            assert message is not None
            return message.id, message.payload["manage_path"].split("=", 1)[1]

    async def job(self, identity: UUID) -> NotificationJob | None:
        async with async_sessionmaker(self.inbox, expire_on_commit=False)() as session:
            return await session.get(NotificationJob, identity)

    async def flush(self) -> None:
        for runner in (self.relay(), self.sender()):
            for _ in range(30):
                if not await runner.run_once():
                    break
            else:
                pytest.fail("Pipeline did not become idle")


@pytest.fixture
async def pipeline(
    databases: tuple[AsyncEngine, AsyncEngine],
) -> AsyncIterator[Pipeline]:
    core, inbox = databases
    app = create_app(
        NotificationSettings(
            database_url=inbox.url.render_as_string(hide_password=False),
            notifications_internal_token=TOKEN,
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client,
    ):
        system = Pipeline(core, inbox, client)
        try:
            yield system
        finally:
            async with inbox.begin() as connection:
                await connection.execute(
                    delete(NotificationJob).where(
                        NotificationJob.payload["payload"]["event_id"].astext.in_(
                            [str(x) for x in system.event_ids]
                        )
                    )
                )
            async with core.begin() as connection:
                await connection.execute(
                    delete(EmailOutbox).where(
                        EmailOutbox.registration_id.in_(
                            select(Registration.id).where(
                                Registration.event_id.in_(system.event_ids)
                            )
                        )
                    )
                )
                await connection.execute(
                    delete(Registration).where(Registration.event_id.in_(system.event_ids))
                )
                await connection.execute(delete(Event).where(Event.id.in_(system.event_ids)))


async def test_cancel_before_core_freeze_never_reaches_smtp_and_resume_issues_current_ticket(
    pipeline: Pipeline,
) -> None:
    event = await pipeline.create()
    identity, token = await pipeline.join(event)
    async with async_sessionmaker(pipeline.core)() as session:
        await registrations.cancel(session, token, 1, pipeline.clock)
    await pipeline.flush()
    assert await pipeline.job(identity) is None
    async with async_sessionmaker(pipeline.core)() as session:
        resumed = await registrations.resume(session, token, 1, pipeline.clock)
    await pipeline.flush()
    assert resumed.participation_no == 2
    async with async_sessionmaker(pipeline.inbox)() as session:
        jobs = (await session.scalars(select(NotificationJob))).all()
        assert len(jobs) == 1 and jobs[0].status == "sent"
        assert jobs[0].payload["payload"]["participation_no"] == 2
        assert resumed.ticket_code is not None
        assert jobs[0].mime is not None
        decoded = BytesParser(policy=policy.default).parsebytes(jobs[0].mime)
        assert resumed.ticket_code in decoded.get_content()


@pytest.mark.parametrize("mime_prepared", [False, True])
async def test_cancel_after_core_freeze_before_or_after_mime_keeps_historical_snapshot(
    pipeline: Pipeline, mime_prepared: bool
) -> None:
    event = await pipeline.create()
    identity, token = await pipeline.join(event)
    assert await pipeline.relay().run_once()
    sender = pipeline.sender()
    frozen = await sender.prepare(identity) if mime_prepared else None
    async with async_sessionmaker(pipeline.core)() as session:
        await registrations.cancel(session, token, 1, pipeline.clock)
    pipeline.now += timedelta(seconds=1)
    await pipeline.flush()
    row = await pipeline.job(identity)
    assert row is not None and row.status == "sent" and row.mime
    if frozen:
        assert row.mime == frozen.data
    async with async_sessionmaker(pipeline.core)() as session:
        view = await registrations.get_registration(session, token)
        assert view.status.value == "cancelled" and view.ticket_code is None
    assert row.payload["payload"]["registration_status"] == "confirmed"


@pytest.mark.parametrize("mime_prepared", [False, True])
async def test_reschedule_after_core_freeze_preserves_original_and_delivers_separate_versions(
    pipeline: Pipeline, mime_prepared: bool
) -> None:
    event = await pipeline.create()
    identity, _ = await pipeline.join(event)
    assert await pipeline.relay().run_once()
    frozen = await pipeline.sender().prepare(identity) if mime_prepared else None
    original = await pipeline.job(identity)
    assert original is not None
    async with async_sessionmaker(pipeline.core)() as session:
        await events.reschedule_event(
            session, event.id, event.starts_at + timedelta(days=1), 1, pipeline.clock
        )
    async with async_sessionmaker(pipeline.core)() as session:
        await events.reschedule_event(
            session, event.id, event.starts_at + timedelta(days=2), 2, pipeline.clock
        )
    pipeline.now += timedelta(seconds=1)
    await pipeline.flush()
    after = await pipeline.job(identity)
    assert after is not None and after.payload == original.payload and after.status == "sent"
    if frozen:
        assert after.mime == frozen.data
    async with async_sessionmaker(pipeline.inbox)() as session:
        jobs = (await session.scalars(select(NotificationJob))).all()
        assert len(jobs) == 3 and all(job.status == "sent" for job in jobs)
        assert {job.payload["payload"]["schedule_version"] for job in jobs} == {1, 2, 3}
    # Original already-delivered job cannot become active through delayed HTTP replay.
    response = await pipeline.http.post(
        "http://notifications/internal/v1/notifications",
        json=original.payload,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 202
    assert not await pipeline.sender().run_once()


async def test_reschedule_before_core_freeze_and_exactly_one_reminder_at_updated_24h_deadline(
    pipeline: Pipeline,
) -> None:
    event = await pipeline.create(days=3)
    identity, _ = await pipeline.join(event)
    new_start = event.starts_at + timedelta(days=2)
    async with async_sessionmaker(pipeline.core)() as session:
        await events.reschedule_event(session, event.id, new_start, 1, pipeline.clock)
    await pipeline.flush()
    row = await pipeline.job(identity)
    assert row is not None and row.payload["payload"]["schedule_version"] == 2
    pipeline.now = new_start - timedelta(hours=24, microseconds=1)
    assert not await pipeline.relay().run_once()
    pipeline.now += timedelta(microseconds=1)
    await pipeline.flush()
    async with async_sessionmaker(pipeline.inbox)() as session:
        jobs = (await session.scalars(select(NotificationJob))).all()
        reminders = [job for job in jobs if job.payload["kind"] == "reminder"]
        assert len(reminders) == 1 and reminders[0].status == "sent"
        assert reminders[0].payload["payload"]["starts_at"] == new_start.isoformat().replace(
            "+00:00", "Z"
        )
    assert not await pipeline.relay().run_once() and not await pipeline.sender().run_once()


@pytest.mark.parametrize("change", ["cancel", "reschedule"])
async def test_smtp_retry_after_business_change_preserves_prepared_mime(
    pipeline: Pipeline, change: str
) -> None:
    from aiosmtplib.errors import SMTPDataError

    event = await pipeline.create()
    identity, token = await pipeline.join(event)
    assert await pipeline.relay().run_once()
    sender = pipeline.sender()

    async def unavailable(_email: object) -> None:
        raise SMTPDataError(451, "temporary failure")

    sender.deliver = unavailable
    assert await sender.run_once()
    before = await pipeline.job(identity)
    assert before is not None and before.mime and before.status == "pending"
    async with async_sessionmaker(pipeline.core)() as session:
        if change == "cancel":
            await registrations.cancel(session, token, 1, pipeline.clock)
        else:
            await events.reschedule_event(
                session, event.id, event.starts_at + timedelta(days=1), 1, pipeline.clock
            )
    pipeline.now = before.available_at
    await pipeline.flush()
    after = await pipeline.job(identity)
    assert after is not None and after.status == "sent" and after.attempts == 2
    assert after.mime == before.mime and after.payload == before.payload
