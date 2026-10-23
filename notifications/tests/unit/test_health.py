from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from notifications_app.config import Settings
from notifications_app.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http


@pytest.mark.parametrize("ready,status", [(True, 200), (False, 503)])
async def test_health_reports_database_schema(
    client: AsyncClient, ready: bool, status: int
) -> None:
    with patch("notifications_app.main.database_is_ready", return_value=ready) as check:
        response = await client.get("/health")
    assert response.status_code == status
    check.assert_awaited_once()
    assert response.json() == {
        "status": "ok" if ready else "unavailable",
        "database": "ready" if ready else "unavailable",
    }


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("SELECT secret", {}, Exception("private-password")),
        OSError("private-password"),
        TimeoutError("private-password"),
    ],
)
async def test_health_does_not_expose_connection_errors(
    client: AsyncClient, error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    with patch("notifications_app.main.database_is_ready", side_effect=error):
        response = await client.get("/health")
    assert response.status_code == 503
    assert "private-password" not in response.text + caplog.text
    assert "SELECT secret" not in response.text + caplog.text
    assert f"Notifications database readiness check failed ({type(error).__name__})" in caplog.text


async def test_infrastructure_exposes_no_delivery_routes(client: AsyncClient) -> None:
    assert (await client.put("/internal/v1/notifications/job", json={})).status_code == 404
    assert (await client.get("/docs")).status_code == 404
