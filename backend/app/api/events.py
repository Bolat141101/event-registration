from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DatabaseSession, RequestClock, organizer_access
from app.api.schemas import CheckIn, CreateEvent, Register, RegistrationAccepted, RescheduleEvent
from app.services import checkins, events, registrations
from app.services.common import EventView, RegistrationView

router = APIRouter(prefix="/events", tags=["events"])
organizer = [Depends(organizer_access)]


@dataclass(frozen=True)
class EventPage:
    items: list[EventView]
    next_offset: int | None
    server_time: datetime


@router.get("")
async def list_events(
    session: DatabaseSession,
    clock: RequestClock,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> EventPage:
    items = await events.list_events(session, limit + 1, offset)
    return EventPage(items[:limit], offset + limit if len(items) > limit else None, clock())


@router.get("/{event_id}")
async def get_event(event_id: UUID, session: DatabaseSession) -> EventView:
    return await events.get_event(session, event_id)


@router.post("", status_code=201, dependencies=organizer)
async def create_event(
    body: CreateEvent, session: DatabaseSession, clock: RequestClock
) -> EventView:
    return await events.create_event(
        session, body.description, body.starts_at, body.capacity, clock
    )


@router.patch("/{event_id}/schedule", dependencies=organizer)
async def reschedule_event(
    event_id: UUID, body: RescheduleEvent, session: DatabaseSession, clock: RequestClock
) -> EventView:
    return await events.reschedule_event(
        session, event_id, body.starts_at, body.expected_schedule_version, clock
    )


@router.post("/{event_id}/registrations", status_code=202)
async def register(
    event_id: UUID, body: Register, session: DatabaseSession, clock: RequestClock
) -> RegistrationAccepted:
    await registrations.register(session, event_id, body.email, clock)
    return RegistrationAccepted()


@router.post("/{event_id}/check-ins", dependencies=organizer)
async def check_in(
    event_id: UUID, body: CheckIn, session: DatabaseSession, clock: RequestClock
) -> RegistrationView:
    return await checkins.check_in(session, event_id, body.ticket_code, clock)
