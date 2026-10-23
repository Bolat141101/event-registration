import secrets
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notifications_app.config import Settings
from notifications_app.contract import NotificationAccepted, NotificationMessage
from notifications_app.inbox import MessageConflict, accept_message

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def internal_access(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    settings = cast(Settings, request.app.state.settings)
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(),
        settings.notifications_internal_token.get_secret_value().encode(),
    ):
        raise HTTPException(status_code=401, detail="Internal authentication required")


@router.post(
    "/internal/v1/notifications",
    status_code=202,
    response_model=NotificationAccepted,
    dependencies=[Depends(internal_access)],
)
async def receive(message: NotificationMessage, request: Request) -> NotificationAccepted:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        try:
            await accept_message(session, message)
        except MessageConflict as exc:
            raise HTTPException(status_code=409, detail="message_id has different content") from exc
    return NotificationAccepted(message_id=message.message_id, status="accepted")
