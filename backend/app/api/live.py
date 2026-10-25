"""Public aggregates only. Private credentials never enter SSE URLs or payloads."""

import json
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.dependencies import RequestClock, organizer_access
from app.clock import Clock
from app.live import LiveCapacityError, LiveHub, Subscription
from app.live import read_event as read_event

router = APIRouter()


async def snapshots(subscription: Subscription, clock: Clock) -> AsyncIterator[str]:
    try:
        while (snapshot := await subscription.queue.get()) is not None:
            data = jsonable_encoder({**asdict(snapshot), "server_time": clock()})
            yield f"retry: 2000\nevent: stats\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    finally:
        await subscription.close()


@router.get(
    "/events/{event_id}/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def event_stream(event_id: UUID, request: Request, clock: RequestClock) -> StreamingResponse:
    hub = cast(LiveHub, request.app.state.live_hub)
    try:
        subscription = await hub.subscribe(event_id)
    except LiveCapacityError:
        raise HTTPException(
            status_code=503, detail="Live capacity reached", headers={"Retry-After": "2"}
        ) from None
    return StreamingResponse(
        snapshots(subscription, clock),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
        background=BackgroundTask(subscription.close),
    )


@router.get("/organizer/access", dependencies=[Depends(organizer_access)])
async def verify_organizer() -> dict[str, str]:
    return {"status": "ok"}
