from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def create_event(
    session: AsyncSession,
    description: str,
    starts_at: datetime,
    capacity: int,
    clock: Clock = utc_now,
) -> EventView:
    starts_at = as_utc(starts_at)
    if not description.strip() or "\x00" in description or not 0 < capacity <= 2_147_483_647:
        raise InvalidInput("invalid_event", "Нужны описание и положительный лимит мест")
    async with session.begin():
        if starts_at <= as_utc(clock()):
            raise Conflict("invalid_start_time", "Дата мероприятия должна быть в будущем")
        event = Event(description=description.strip(), starts_at=starts_at, capacity=capacity)
        session.add(event)
        await session.flush()
        return await event_view(session, event.id)


async def list_events(session: AsyncSession) -> list[EventView]:
    async with session.begin():
        return await event_views(session)


async def get_event(session: AsyncSession, event_id: UUID) -> EventView:
    async with session.begin():
        return await event_view(session, event_id)


async def reschedule_event(
    session: AsyncSession,
    event_id: UUID,
    starts_at: datetime,
    expected_schedule_version: int,
    clock: Clock = utc_now,
) -> EventView:
    starts_at = as_utc(starts_at)
    async with session.begin():
        event = await lock_event(session, event_id)
        now = as_utc(clock())
        if starts_at == event.starts_at:
            return await event_view(session, event_id)
        if expected_schedule_version != event.schedule_version:
            raise Conflict("schedule_version_conflict", "Дата уже изменена; обновите мероприятие")
        require_before_start(event, now)
        if starts_at <= now:
            raise Conflict("invalid_start_time", "Новая дата должна быть в будущем")
        old_starts_at = event.starts_at
        event.starts_at = starts_at
        event.schedule_version += 1
        entries = (
            await session.scalars(
                select(Registration).where(
                    Registration.event_id == event_id,
                    Registration.status != RegistrationStatus.CANCELLED,
                )
            )
        ).all()
        for entry in entries:
            await queue_reschedule(session, entry, event, old_starts_at, now)
        await session.flush()
        return await event_view(session, event_id)
