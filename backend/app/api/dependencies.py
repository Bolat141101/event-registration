import secrets
from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock
from app.config import Settings
from app.services.errors import Unauthorized

bearer = HTTPBearer(auto_error=False)
type Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def session_dependency(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session


def clock_dependency(request: Request) -> Clock:
    return cast(Clock, request.app.state.clock)


def participant_token(credentials: Credentials) -> str:
    if credentials is None or len(credentials.credentials) > 256:
        raise Unauthorized("authentication_required", "Нужен Bearer-токен")
    return credentials.credentials


def organizer_access(request: Request, credentials: Credentials) -> None:
    settings = cast(Settings, request.app.state.settings)
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(), settings.organizer_token.get_secret_value().encode()
    ):
        raise Unauthorized("invalid_organizer_token", "Неверный ключ организатора")


type DatabaseSession = Annotated[Session, Depends(session_dependency)]
type RequestClock = Annotated[Clock, Depends(clock_dependency)]
type ParticipantToken = Annotated[str, Depends(participant_token)]
