import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, DisconnectionError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.services.errors import Conflict, DomainError, InvalidInput, NotFound, Unauthorized

logger = logging.getLogger(__name__)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        status = 400
        if isinstance(exc, Unauthorized):
            status = 401
        elif isinstance(exc, NotFound):
            status = 404
        elif isinstance(exc, Conflict):
            status = 409
        elif isinstance(exc, InvalidInput):
            status = 422
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return JSONResponse(
            status_code=status,
            content={"code": exc.code, "message": exc.message},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "Проверьте поля запроса",
                "errors": [
                    {"loc": error["loc"], "type": error["type"], "message": error["msg"]}
                    for error in exc.errors()
                ],
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        sqlstate = getattr(exc.orig, "sqlstate", "") if isinstance(exc, DBAPIError) else ""
        temporary = isinstance(exc, (OperationalError, DisconnectionError, PoolTimeout)) or (
            sqlstate in {"55P03", "57014", "40P01", "40001"}
            or bool(sqlstate and sqlstate.startswith("08"))
        )
        # Never log SQL parameters, Authorization, email payloads or exception text.
        logger.warning("Database operation failed; temporary=%s", temporary)
        return JSONResponse(
            status_code=503 if temporary else 500,
            content={
                "code": "database_unavailable" if temporary else "database_error",
                "message": "База данных временно недоступна" if temporary else "Ошибка базы данных",
            },
            headers={"Retry-After": "1"} if temporary else None,
        )
