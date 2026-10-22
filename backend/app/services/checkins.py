from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, as_utc, utc_now
from app.db.models import Registration, RegistrationStatus
from app.services.common import RegistrationView, lock_event, registration_view
from app.services.errors import Conflict, NotFound


async def check_in(
    session: AsyncSession, event_id: UUID, ticket_code: str, clock: Clock = utc_now
) -> RegistrationView:
    async with session.begin():
        event = await lock_event(session, event_id)
        now = as_utc(clock())
        if now < event.starts_at:
            raise Conflict("checkin_not_started", "Чекин доступен с начала мероприятия")
        entry = await session.scalar(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.ticket_code == ticket_code,
                Registration.status == RegistrationStatus.CONFIRMED,
            )
        )
        if entry is None:
            raise NotFound("ticket_not_found", "Действующий билет не найден")
        updated = (
            await session.execute(
                update(Registration)
                .where(Registration.id == entry.id, Registration.checked_in_at.is_(None))
                .values(checked_in_at=now)
                .returning(Registration.id)
            )
        ).scalar_one_or_none()
        if updated is None:
            raise Conflict("already_checked_in", "Участник уже прошёл чекин")
        await session.refresh(entry)
        return registration_view(entry)
