import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from notifications_app.config import Settings
from notifications_app.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.mark.parametrize("target", ["own", "core", "missing", "bad_password"])
async def test_health_checks_actual_connection_and_role(
    integration_engine: AsyncEngine, target: str
) -> None:
    url = integration_engine.url
    if target == "core":
        url = url.set(database=make_url(os.environ["TEST_CORE_DATABASE_URL"]).database)
    elif target == "missing":
        url = url.set(database="nonexistent_notifications_health_test")
    elif target == "bad_password":
        url = url.set(password="intentionally-wrong-password")
    app = create_app(Settings(database_url=url.render_as_string(hide_password=False)))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health")
    assert response.status_code == (200 if target == "own" else 503)
    assert response.json() == {
        "status": "ok" if target == "own" else "unavailable",
        "database": "ready" if target == "own" else "unavailable",
    }
    assert "intentionally-wrong-password" not in response.text
