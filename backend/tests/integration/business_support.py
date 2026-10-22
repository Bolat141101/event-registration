from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic, sleep
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, delete, select, text
from sqlalchemy.orm import Session

from app.db.models import EmailOutbox, Event, Registration
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
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.clock = FakeClock()
        self.event_ids: list[UUID] = []

    def create(self, capacity: int = 1, starts_at: datetime | None = None) -> EventView:
        with Session(self.engine) as session:
            item = events.create_event(
                session,
                "Описание события",
                starts_at or self.clock() + timedelta(days=2),
                capacity,
                self.clock,
            )
        self.event_ids.append(item.id)
        return item

    def join(self, event_id: UUID, email: str) -> Participant:
        with Session(self.engine) as session:
            registrations.register(session, event_id, email, self.clock)
            entry = session.scalars(
                select(Registration).where(
                    Registration.event_id == event_id, Registration.email == email.strip().lower()
                )
            ).one()
            messages = session.scalars(
                select(EmailOutbox).where(EmailOutbox.registration_id == entry.id)
            ).all()
            first = next(message for message in messages if "manage_path" in message.payload)
            return Participant(entry.id, first.payload["manage_path"].split("#token=", 1)[1])

    def private(self, person: Participant) -> RegistrationView:
        with Session(self.engine) as session:
            return registrations.get_registration(session, person.token)

    def cancel(self, person: Participant, version: int = 1) -> RegistrationView:
        with Session(self.engine) as session:
            return registrations.cancel(session, person.token, version, self.clock)

    def resume(self, person: Participant, version: int = 1) -> RegistrationView:
        with Session(self.engine) as session:
            return registrations.resume(session, person.token, version, self.clock)

    def checkin(self, event_id: UUID, ticket: str) -> RegistrationView:
        with Session(self.engine) as session:
            return checkins.check_in(session, event_id, ticket, self.clock)

    def schedule(self, event_id: UUID, starts_at: datetime, version: int) -> EventView:
        with Session(self.engine) as session:
            return events.reschedule_event(session, event_id, starts_at, version, self.clock)

    def event(self, event_id: UUID) -> EventView:
        with Session(self.engine) as session:
            return events.get_event(session, event_id)

    def messages(self, person: Participant) -> list[EmailOutbox]:
        with Session(self.engine) as session:
            return list(
                session.scalars(
                    select(EmailOutbox)
                    .where(EmailOutbox.registration_id == person.id)
                    .order_by(EmailOutbox.kind, EmailOutbox.dedup_key)
                )
            )

    def cleanup(self) -> None:
        with self.engine.begin() as connection:
            ids = select(Registration.id).where(Registration.event_id.in_(self.event_ids))
            connection.execute(delete(EmailOutbox).where(EmailOutbox.registration_id.in_(ids)))
            connection.execute(
                delete(Registration).where(Registration.event_id.in_(self.event_ids))
            )
            connection.execute(delete(Event).where(Event.id.in_(self.event_ids)))


def parallel_while_event_locked(
    business: Business,
    event_id: UUID,
    *operations: Callable[[], Any],
    before_release: Callable[[], None] | None = None,
) -> list[Any]:
    """Force real concurrent transactions to wait in PostgreSQL before release."""

    def invoke(operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except DomainError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=len(operations)) as executor:
        with Session(business.engine) as blocker, blocker.begin():
            blocker.execute(select(Event.id).where(Event.id == event_id).with_for_update())
            futures = [executor.submit(invoke, operation) for operation in operations]
            deadline = monotonic() + 8
            with business.engine.connect() as observer:
                while monotonic() < deadline:
                    blocked = observer.execute(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                            "AND cardinality(pg_blocking_pids(pid)) > 0"
                        )
                    ).scalar_one()
                    if blocked >= len(operations):
                        break
                    sleep(0.01)
                else:
                    raise AssertionError("Business transactions did not block concurrently")
            if before_release is not None:
                before_release()
        return [future.result(timeout=10) for future in futures]
