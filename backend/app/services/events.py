from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import Clock, as_utc, utc_now
from app.db.models import Event, Registration, RegistrationStatus
from app.notifications.outbox import queue_reschedule
from app.services.common import (
    EventView,
    event_view,
    event_views,
    lock_event,
    require_before_start,
)
from app.services.errors import Conflict, InvalidInput


def create_event(
    session: Session, description: str, starts_at: datetime, capacity: int, clock: Clock = utc_now
) -> EventView:
    starts_at = as_utc(starts_at)
    if not description.strip() or "\x00" in description or not 0 < capacity <= 2_147_483_647:
        raise InvalidInput("invalid_event", "Нужны описание и положительный лимит мест")
    with session.begin():
        if starts_at <= as_utc(clock()):
            raise Conflict("invalid_start_time", "Дата мероприятия должна быть в будущем")
        event = Event(description=description.strip(), starts_at=starts_at, capacity=capacity)
        session.add(event)
        session.flush()
        return event_view(session, event.id)


def list_events(session: Session) -> list[EventView]:
    with session.begin():
        return event_views(session)


def get_event(session: Session, event_id: UUID) -> EventView:
    with session.begin():
        return event_view(session, event_id)


def reschedule_event(
    session: Session,
    event_id: UUID,
    starts_at: datetime,
    expected_schedule_version: int,
    clock: Clock = utc_now,
) -> EventView:
    starts_at = as_utc(starts_at)
    with session.begin():
        event = lock_event(session, event_id)
        now = as_utc(clock())
        if starts_at == event.starts_at:
            return event_view(session, event_id)
        if expected_schedule_version != event.schedule_version:
            raise Conflict("schedule_version_conflict", "Дата уже изменена; обновите мероприятие")
        require_before_start(event, now)
        if starts_at <= now:
            raise Conflict("invalid_start_time", "Новая дата должна быть в будущем")
        old_starts_at = event.starts_at
        event.starts_at = starts_at
        event.schedule_version += 1
        entries = session.scalars(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.status != RegistrationStatus.CANCELLED,
            )
        ).all()
        for entry in entries:
            queue_reschedule(session, entry, event, old_starts_at, now)
        session.flush()
        return event_view(session, event_id)
