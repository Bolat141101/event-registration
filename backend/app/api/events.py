from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import DatabaseSession, RequestClock, organizer_access
from app.api.schemas import CheckIn, CreateEvent, Register, RegistrationAccepted, RescheduleEvent
from app.services import checkins, events, registrations
from app.services.common import EventView, RegistrationView

router = APIRouter(prefix="/events", tags=["events"])
organizer = [Depends(organizer_access)]


@router.get("")
def list_events(session: DatabaseSession) -> list[EventView]:
    return events.list_events(session)


@router.get("/{event_id}")
def get_event(event_id: UUID, session: DatabaseSession) -> EventView:
    return events.get_event(session, event_id)


@router.post("", status_code=201, dependencies=organizer)
def create_event(body: CreateEvent, session: DatabaseSession, clock: RequestClock) -> EventView:
    return events.create_event(session, body.description, body.starts_at, body.capacity, clock)


@router.patch("/{event_id}/schedule", dependencies=organizer)
def reschedule_event(
    event_id: UUID, body: RescheduleEvent, session: DatabaseSession, clock: RequestClock
) -> EventView:
    return events.reschedule_event(
        session, event_id, body.starts_at, body.expected_schedule_version, clock
    )


@router.post("/{event_id}/registrations", status_code=202)
def register(
    event_id: UUID, body: Register, session: DatabaseSession, clock: RequestClock
) -> RegistrationAccepted:
    registrations.register(session, event_id, body.email, clock)
    return RegistrationAccepted()


@router.post("/{event_id}/check-ins", dependencies=organizer)
def check_in(
    event_id: UUID, body: CheckIn, session: DatabaseSession, clock: RequestClock
) -> RegistrationView:
    return checkins.check_in(session, event_id, body.ticket_code, clock)
