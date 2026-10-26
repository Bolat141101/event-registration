import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.models import EmailOutbox, Event, Registration
from app.email_addresses import canonical_email
from app.services import checkins, events, registrations
from app.services.common import EventView, RegistrationView
from app.services.errors import DomainError


@dataclass
class FakeClock:
    now: datetime = datetime(2030, 1, 1, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@dataclass(frozen=True)
class Participant:
    id: UUID
    token: str


class Business:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.clock = FakeClock()
        self.event_ids: list[UUID] = []

    async def create(self, capacity: int = 1, starts_at: datetime | None = None) -> EventView:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            item = await events.create_event(
                session,
                "Event description",
                starts_at or self.clock() + timedelta(days=2),
                capacity,
                self.clock,
            )
        self.event_ids.append(item.id)
        return item

    async def join(self, event_id: UUID, email: str) -> Participant:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            await registrations.register(session, event_id, email, self.clock)
            entry = (
                await session.scalars(
                    select(Registration).where(
                        Registration.event_id == event_id,
                        Registration.email == canonical_email(email),
                    )
                )
            ).one()
            messages = (
                await session.scalars(
                    select(EmailOutbox).where(EmailOutbox.registration_id == entry.id)
                )
            ).all()
            first = next(message for message in messages if "manage_path" in message.payload)
            return Participant(entry.id, first.payload["manage_path"].split("#token=", 1)[1])

    async def private(self, person: Participant) -> RegistrationView:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            return await registrations.get_registration(session, person.token)

    async def cancel(self, person: Participant, version: int = 1) -> RegistrationView:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            return await registrations.cancel(session, person.token, version, self.clock)

    async def resume(self, person: Participant, version: int = 1) -> RegistrationView:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            return await registrations.resume(session, person.token, version, self.clock)

    async def checkin(self, event_id: UUID, ticket: str) -> RegistrationView:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            return await checkins.check_in(session, event_id, ticket, self.clock)

    async def schedule(self, event_id: UUID, starts_at: datetime, version: int) -> EventView:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            return await events.reschedule_event(session, event_id, starts_at, version, self.clock)

    async def event(self, event_id: UUID) -> EventView:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            return await events.get_event(session, event_id)

    async def messages(self, person: Participant) -> list[EmailOutbox]:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            return list(
                await session.scalars(
                    select(EmailOutbox)
                    .where(EmailOutbox.registration_id == person.id)
                    .order_by(EmailOutbox.kind, EmailOutbox.dedup_key)
                )
            )

    async def cleanup(self) -> None:
        async with self.engine.begin() as connection:
            ids = select(Registration.id).where(Registration.event_id.in_(self.event_ids))
            (
                await connection.execute(
                    delete(EmailOutbox).where(EmailOutbox.registration_id.in_(ids))
                )
            )
            (
                await connection.execute(
                    delete(Registration).where(Registration.event_id.in_(self.event_ids))
                )
            )
            await connection.execute(delete(Event).where(Event.id.in_(self.event_ids)))


async def parallel_while_event_locked(
    business: Business,
    event_id: UUID,
    *operations: Callable[[], Awaitable[Any]],
    before_release: Callable[[], None] | None = None,
) -> list[Any]:
    """Run independent asyncio tasks and observe real PostgreSQL lock contention."""

    async def invoke(operation: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await operation()
        except DomainError as exc:
            return exc

    async with (
        asyncio.TaskGroup() as group,
        AsyncSession(business.engine) as blocker,
        blocker.begin(),
    ):
        await blocker.execute(select(Event.id).where(Event.id == event_id).with_for_update())
        tasks = [group.create_task(invoke(operation)) for operation in operations]
        deadline = monotonic() + 8
        async with business.engine.connect() as observer:
            while monotonic() < deadline:
                # pg_stat_activity caches its snapshot inside an observer transaction.
                await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                blocked = (
                    await observer.execute(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                            "AND cardinality(pg_blocking_pids(pid)) > 0"
                        )
                    )
                ).scalar_one()
                if blocked >= len(operations):
                    break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError("Business transactions did not block concurrently")
        if before_release is not None:
            before_release()
    return [task.result() for task in tasks]
