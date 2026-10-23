"""Public snapshots only; never keep a session open while waiting for a client."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import cast
from uuid import UUID

from anyio import CancelScope
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import RequestClock, organizer_access
from app.clock import Clock
from app.services import events
from app.services.common import EventView

router = APIRouter()
logger = logging.getLogger(__name__)


async def read_event(sessions: async_sessionmaker[AsyncSession], event_id: UUID) -> EventView:
    # ASGI disconnects use level cancellation. Finish this short read AND close
    # the asyncpg session before cancellation resumes; no shield crosses a yield.
    with CancelScope(shield=True):
        async with sessions() as session:
            return await events.get_event(session, event_id)
    raise asyncio.CancelledError  # Preserve cancellation if this scope itself is cancelled.


async def snapshots(
    request: Request,
    sessions: async_sessionmaker[AsyncSession],
    event_id: UUID,
    clock: Clock,
    initial: EventView,
) -> AsyncIterator[str]:
    snapshot = initial
    while not await request.is_disconnected():
        # Every tick is also a heartbeat. Full snapshots recover without replay,
        # and let a participant reread their private state even if totals match.
        data = jsonable_encoder({**asdict(snapshot), "server_time": clock()})
        yield f"retry: 2000\nevent: stats\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        await asyncio.sleep(1)
        if await request.is_disconnected():
            return
        try:
            snapshot = await read_event(sessions, event_id)
        except (SQLAlchemyError, OSError):
            logger.warning("Live snapshot unavailable; closing stream")
            return


@router.get(
    "/events/{event_id}/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def event_stream(event_id: UUID, request: Request, clock: RequestClock) -> StreamingResponse:
    sessions = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    initial = await read_event(sessions, event_id)  # 404/503 before response headers.
    return StreamingResponse(
        snapshots(request, sessions, event_id, clock, initial),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/organizer/access", dependencies=[Depends(organizer_access)])
async def verify_organizer() -> dict[str, str]:
    # Verify the existing shared key without a fake business mutation/session.
    return {"status": "ok"}
