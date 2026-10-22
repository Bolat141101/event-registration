import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event, Registration, RegistrationStatus
from app.services.errors import Conflict, InvalidInput, NotFound, Unauthorized


@dataclass(frozen=True)
class EventView:
    id: UUID
    description: str
    starts_at: datetime
    capacity: int
    schedule_version: int
    confirmed: int
    waitlisted: int
    checked_in: int


@dataclass(frozen=True)
class RegistrationView:
    id: UUID
    event_id: UUID
    status: RegistrationStatus
    participation_no: int
    waitlist_seq: int | None
    ticket_code: str | None
    checked_in_at: datetime | None


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    try:
        # Local operation: no DNS/API requests. .test domains work in Mailpit.
        validate_email(
            normalized, check_deliverability=False, test_environment=True, allow_smtputf8=False
        )
    except EmailNotValidError as exc:
        raise InvalidInput("invalid_email", "Укажите корректный email") from exc
    return normalized


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def lock_event(session: AsyncSession, event_id: UUID) -> Event:
    with session.no_autoflush:
        event = await session.scalar(
            select(Event)
            .where(Event.id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if event is None:
        raise NotFound("event_not_found", "Мероприятие не найдено")
    return event


def require_before_start(event: Event, now: datetime) -> None:
    if now >= event.starts_at:
        raise Conflict("event_started", "Мероприятие уже началось")


def registration_view(entry: Registration) -> RegistrationView:
    return RegistrationView(
        entry.id,
        entry.event_id,
        entry.status,
        entry.participation_no,
        entry.waitlist_seq,
        entry.ticket_code,
        entry.checked_in_at,
    )


async def find_registration(session: AsyncSession, token: str) -> Registration:
    entry = await session.scalar(
        select(Registration)
        .where(Registration.manage_token_hash == token_hash(token))
        .execution_options(populate_existing=True)
    )
    if entry is None:
        raise Unauthorized("invalid_participant_token", "Неверный токен участника")
    return entry


async def event_views(session: AsyncSession, event_id: UUID | None = None) -> list[EventView]:
    query = (
        select(
            Event.id,
            Event.description,
            Event.starts_at,
            Event.capacity,
            Event.schedule_version,
            func.count(Registration.id).filter(Registration.status == RegistrationStatus.CONFIRMED),
            func.count(Registration.id).filter(
                Registration.status == RegistrationStatus.WAITLISTED
            ),
            func.count(Registration.id).filter(Registration.checked_in_at.is_not(None)),
        )
        .outerjoin(Registration, Registration.event_id == Event.id)
        .group_by(Event.id)
        .order_by(Event.starts_at, Event.id)
    )
    if event_id is not None:
        query = query.where(Event.id == event_id)
    return [EventView(*row) for row in (await session.execute(query))]


async def event_view(session: AsyncSession, event_id: UUID) -> EventView:
    views = await event_views(session, event_id)
    if not views:
        raise NotFound("event_not_found", "Мероприятие не найдено")
    return views[0]
