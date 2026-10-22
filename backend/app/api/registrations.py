from fastapi import APIRouter

from app.api.dependencies import DatabaseSession, ParticipantToken, RequestClock
from app.api.schemas import ParticipationChange
from app.services import registrations
from app.services.common import RegistrationView

router = APIRouter(prefix="/registration", tags=["registration"])


@router.get("")
def get_registration(session: DatabaseSession, token: ParticipantToken) -> RegistrationView:
    return registrations.get_registration(session, token)


@router.post("/cancel")
def cancel(
    body: ParticipationChange,
    session: DatabaseSession,
    token: ParticipantToken,
    clock: RequestClock,
) -> RegistrationView:
    return registrations.cancel(session, token, body.expected_participation_no, clock)


@router.post("/resume")
def resume(
    body: ParticipationChange,
    session: DatabaseSession,
    token: ParticipantToken,
    clock: RequestClock,
) -> RegistrationView:
    return registrations.resume(session, token, body.expected_participation_no, clock)
