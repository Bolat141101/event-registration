import secrets
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, as_utc, utc_now
from app.db.models import Event, Registration, RegistrationStatus
from app.db.waitlist import next_waitlist_seq
from app.notifications.outbox import (
    cancel_unprepared,
    queue_participation_notice,
    refresh_unprepared_notices,
    sync_reminder,
)
from app.services.common import (
    RegistrationView,
    find_registration,
    lock_event,
    normalize_email,
    registration_view,
    require_before_start,
    token_hash,
)
from app.services.errors import Conflict, Unauthorized


async def confirmed_count(session: AsyncSession, event: Event) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.event_id == event.id,
                Registration.status == RegistrationStatus.CONFIRMED,
            )
        )
    ).scalar_one()


async def fill_vacancies(session: AsyncSession, event: Event, now: datetime) -> None:
    available = event.capacity - (await confirmed_count(session, event))
    if available <= 0:
        return
    waiting = (
        await session.scalars(
            select(Registration)
            .where(
                Registration.event_id == event.id,
                Registration.status == RegistrationStatus.WAITLISTED,
            )
            .order_by(Registration.waitlist_seq)
            .limit(available)
        )
    ).all()
    for entry in waiting:
        entry.status = RegistrationStatus.CONFIRMED
        entry.waitlist_seq = None
        entry.ticket_code = secrets.token_urlsafe(24)
        await session.flush()
        await refresh_unprepared_notices(session, entry, event)
        await queue_participation_notice(session, entry, event, now)
        await sync_reminder(session, entry, event, now)


async def assign_place(session: AsyncSession, entry: Registration, event: Event) -> None:
    if (await confirmed_count(session, event)) < event.capacity:
        entry.status = RegistrationStatus.CONFIRMED
        entry.waitlist_seq = None
        entry.ticket_code = secrets.token_urlsafe(24)
    else:
        position = await next_waitlist_seq(session, event.id)
        entry.status = RegistrationStatus.WAITLISTED
        entry.ticket_code = None
        entry.waitlist_seq = position


async def register(
    session: AsyncSession, event_id: UUID, email: str, clock: Clock = utc_now
) -> None:
    email = normalize_email(email)
    async with session.begin():
        event = await lock_event(session, event_id)
        now = as_utc(clock())
        existing = await session.scalar(
            select(Registration.id).where(
                Registration.event_id == event_id, Registration.email == email
            )
        )
        if existing is not None:
            return
        # Keep the response neutral even after registration closes: a different
        # result for a new address would disclose whether this email is stored.
        if now >= event.starts_at:
            return
        await fill_vacancies(session, event, now)
        token = secrets.token_urlsafe(32)
        entry = Registration(event_id=event_id, email=email, manage_token_hash=token_hash(token))
        await assign_place(session, entry, event)
        session.add(entry)
        await session.flush()
        await queue_participation_notice(session, entry, event, now, initial_token=token)
        await sync_reminder(session, entry, event, now)


async def get_registration(session: AsyncSession, token: str) -> RegistrationView:
    async with session.begin():
        return registration_view(await find_registration(session, token))


async def locked_registration(session: AsyncSession, token: str) -> tuple[Event, Registration]:
    # Discover only the event ID, then reread registration after obtaining its lock.
    event_id = await session.scalar(
        select(Registration.event_id).where(Registration.manage_token_hash == token_hash(token))
    )
    if event_id is None:
        raise Unauthorized("invalid_participant_token", "Неверный токен участника")
    event = await lock_event(session, event_id)
    return event, (await find_registration(session, token))


async def cancel(
    session: AsyncSession, token: str, expected_participation_no: int, clock: Clock = utc_now
) -> RegistrationView:
    async with session.begin():
        event, entry = await locked_registration(session, token)
        now = as_utc(clock())
        if expected_participation_no != entry.participation_no:
            raise Conflict("participation_conflict", "Участие изменилось; обновите регистрацию")
        if entry.status == RegistrationStatus.CANCELLED:
            return registration_view(entry)
        if entry.checked_in_at is not None:
            raise Conflict("already_checked_in", "Участник уже прошёл чекин")
        require_before_start(event, now)
        was_confirmed = entry.status == RegistrationStatus.CONFIRMED
        entry.status = RegistrationStatus.CANCELLED
        entry.ticket_code = None
        entry.waitlist_seq = None
        await session.flush()
        await cancel_unprepared(session, entry)
        if was_confirmed:
            await fill_vacancies(session, event, now)
        return registration_view(entry)


async def resume(
    session: AsyncSession, token: str, expected_participation_no: int, clock: Clock = utc_now
) -> RegistrationView:
    async with session.begin():
        event, entry = await locked_registration(session, token)
        now = as_utc(clock())
        if (
            entry.participation_no == expected_participation_no + 1
            and entry.status != RegistrationStatus.CANCELLED
        ):
            return registration_view(entry)
        if (
            entry.participation_no != expected_participation_no
            or entry.status != RegistrationStatus.CANCELLED
        ):
            raise Conflict("participation_conflict", "Участие изменилось; обновите регистрацию")
        require_before_start(event, now)
        await fill_vacancies(session, event, now)
        entry.participation_no += 1
        await assign_place(session, entry, event)
        await session.flush()
        await queue_participation_notice(session, entry, event, now)
        await sync_reminder(session, entry, event, now)
        return registration_view(entry)
