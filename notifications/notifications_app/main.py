import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from notifications_app.api import router
from notifications_app.config import Settings
from notifications_app.db import build_engine, build_session_factory
from notifications_app.health import database_is_ready, expected_schema_heads

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ready", "unavailable"]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(settings)
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
        app.state.schema_heads = expected_schema_heads()
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="Notifications infrastructure",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def invalid_contract(_request: Request, _error: RequestValidationError) -> JSONResponse:
        # Validation errors must not echo recipient addresses or management tokens.
        return JSONResponse(status_code=422, content={"detail": "Invalid notification contract"})

    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request, response: Response) -> HealthResponse:
        try:
            ready = await database_is_ready(
                request.app.state.engine, request.app.state.schema_heads
            )
        except Exception as exc:
            # Connection/authentication errors can escape asyncpg before SQLAlchemy
            # wraps them. Any failed readiness check means 503; never log the DSN.
            logger.warning("Notifications database readiness check failed (%s)", type(exc).__name__)
            ready = False
        if not ready:
            response.status_code = 503
            return HealthResponse(status="unavailable", database="unavailable")
        return HealthResponse(status="ok", database="ready")

    return app
