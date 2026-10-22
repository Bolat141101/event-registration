import logging
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.db.health import database_is_ready

logger = logging.getLogger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ready", "unavailable"]


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, response: Response) -> HealthResponse:
    try:
        ready = await database_is_ready(request.app.state.engine, request.app.state.schema_heads)
    except (SQLAlchemyError, OSError, TimeoutError):
        logger.warning("Database readiness check failed")
        ready = False
    if not ready:
        response.status_code = 503
        return HealthResponse(status="unavailable", database="unavailable")
    return HealthResponse(status="ok", database="ready")
