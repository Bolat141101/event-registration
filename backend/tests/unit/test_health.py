from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http


async def test_health_success(client: AsyncClient) -> None:
    with patch("app.api.health.database_is_ready", return_value=True):
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ready"}


async def test_health_rejects_stale_schema(client: AsyncClient) -> None:
    with patch("app.api.health.database_is_ready", return_value=False):
        response = await client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}


async def test_database_error_does_not_expose_credentials(client: AsyncClient) -> None:
    error = OperationalError("SELECT 1", {}, Exception("password=private-password"))
    with patch("app.api.health.database_is_ready", side_effect=error):
        response = await client.get("/api/health")
    assert response.status_code == 503
    assert "private-password" not in response.text
