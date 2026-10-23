import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine

from notifications_app.config import Settings
from notifications_app.main import create_app
from notifications_app.models import JobStatus, NotificationJob

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
TOKEN = "test_notifications_internal_token_32_characters_minimum"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PATH = "/internal/v1/notifications"


@pytest.fixture
async def identities(integration_engine: AsyncEngine) -> AsyncIterator[list[UUID]]:
    items = [uuid4() for _ in range(4)]
    try:
        yield items
    finally:
        async with integration_engine.begin() as connection:
            await connection.execute(delete(NotificationJob).where(NotificationJob.id.in_(items)))


@pytest.fixture
def document(identities: list[UUID]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "message_id": str(identities[0]),
        "registration_id": str(uuid4()),
        "kind": "ticket",
        "payload": {
            "recipient": "user@example.test",
            "event_id": str(uuid4()),
            "description": "Событие",
            "starts_at": "2030-01-03T12:00:00Z",
            "schedule_version": 1,
            "participation_no": 1,
            "registration_status": "confirmed",
            "ticket_code": "ticket-secret",
            "manage_path": "/registration#token=private-token",
        },
    }


def settings_for(engine: AsyncEngine) -> Settings:
    return Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        notifications_internal_token=TOKEN,
    )


@pytest.fixture
async def client(integration_engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings_for(integration_engine))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://notifications"
        ) as http,
    ):
        yield http


@pytest.mark.parametrize(
    "authorization", [None, "", "Bearer wrong", "Basic secret", "Bearer " + "x" * 40]
)
async def test_internal_auth_required_before_persistence(
    client: httpx.AsyncClient,
    document: dict[str, Any],
    integration_engine: AsyncEngine,
    authorization: str | None,
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = await client.post(PATH, json=document, headers=headers)
    assert response.status_code == 401
    async with integration_engine.connect() as connection:
        assert (
            await connection.scalar(
                select(NotificationJob.id).where(NotificationJob.id == UUID(document["message_id"]))
            )
            is None
        )


async def test_commits_before_ack_and_duplicate_never_overwrites_delivery_state(
    client: httpx.AsyncClient, document: dict[str, Any], integration_engine: AsyncEngine
) -> None:
    response = await client.post(PATH, json=document, headers=HEADERS)
    assert response.status_code == 202
    assert response.json() == {"message_id": document["message_id"], "status": "accepted"}
    identity = UUID(document["message_id"])
    async with integration_engine.begin() as connection:
        row = (
            (
                await connection.execute(
                    select(NotificationJob).where(NotificationJob.id == identity)
                )
            )
            .mappings()
            .one()
        )
        assert row["status"] == JobStatus.PENDING and row["mime"] is None
        assert row["payload"]["message_id"] == document["message_id"]
        await connection.execute(
            NotificationJob.__table__.update()
            .where(NotificationJob.id == identity)
            .values(status="sent", mime=b"fixed MIME", attempts=2, last_error="historical error")
        )
    assert (await client.post(PATH, json=document, headers=HEADERS)).status_code == 202
    async with integration_engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    select(NotificationJob).where(NotificationJob.id == identity)
                )
            )
            .mappings()
            .one()
        )
        assert row["status"] == "sent" and row["mime"] == b"fixed MIME"
        assert row["attempts"] == 2 and row["last_error"] == "historical error"


async def test_concurrent_identical_delivery_is_one_job(
    client: httpx.AsyncClient, document: dict[str, Any], integration_engine: AsyncEngine
) -> None:
    responses = await asyncio.gather(
        *(client.post(PATH, json=document, headers=HEADERS) for _ in range(16))
    )
    assert [response.status_code for response in responses] == [202] * 16
    async with integration_engine.connect() as connection:
        assert (
            len(
                (
                    await connection.scalars(
                        select(NotificationJob.id).where(
                            NotificationJob.id == UUID(document["message_id"])
                        )
                    )
                ).all()
            )
            == 1
        )


async def test_concurrent_different_content_is_conflict(
    client: httpx.AsyncClient, document: dict[str, Any], integration_engine: AsyncEngine
) -> None:
    changed = deepcopy(document)
    changed["payload"]["description"] = "Другое событие"
    responses = await asyncio.gather(
        client.post(PATH, json=document, headers=HEADERS),
        client.post(PATH, json=changed, headers=HEADERS),
    )
    assert sorted(response.status_code for response in responses) == [202, 409]
    async with integration_engine.connect() as connection:
        saved = await connection.scalar(
            select(NotificationJob.payload).where(
                NotificationJob.id == UUID(document["message_id"])
            )
        )
        winner = document if responses[0].status_code == 202 else changed
        assert saved["payload"]["description"] == winner["payload"]["description"]


@pytest.mark.parametrize("change", ["recipient", "kind", "generation", "message_version"])
async def test_same_id_with_different_content_is_409(
    client: httpx.AsyncClient, document: dict[str, Any], change: str
) -> None:
    assert (await client.post(PATH, json=document, headers=HEADERS)).status_code == 202
    altered = deepcopy(document)
    if change == "recipient":
        altered["payload"]["recipient"] = "other@example.test"
    elif change == "kind":
        altered["kind"] = "reminder"
    else:
        altered["payload"]["participation_no" if change == "generation" else "schedule_version"] = 2
    assert (await client.post(PATH, json=altered, headers=HEADERS)).status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "bool_version",
        "null",
        "date_max",
        "date_min",
        "unknown",
        "ticket",
        "naive",
        "reschedule",
        "numeric_date",
    ],
)
async def test_invalid_contract_returns_safe_422(
    client: httpx.AsyncClient, document: dict[str, Any], change: str
) -> None:
    if change == "version":
        document["schema_version"] = 2
    elif change == "bool_version":
        document["schema_version"] = True
    elif change == "null":
        document["payload"]["description"] += "\x00"
    elif change == "date_max":
        document["payload"]["starts_at"] = "9999-12-31T23:59:59-01:00"
    elif change == "date_min":
        document["payload"]["starts_at"] = "0001-01-01T00:00:00+01:00"
    elif change == "unknown":
        document["extra"] = 1
    elif change == "ticket":
        document["payload"]["ticket_code"] = None
    elif change == "numeric_date":
        document["payload"]["starts_at"] = 1234
    elif change == "naive":
        document["payload"]["starts_at"] = "2030-01-03T12:00:00"
    else:
        document["kind"] = "rescheduled"
    response = await client.post(PATH, json=document, headers=HEADERS)
    assert response.status_code == 422
    assert "private-token" not in response.text and "user@example.test" not in response.text


async def test_old_and_out_of_order_snapshots_are_accepted_without_overwrite(
    client: httpx.AsyncClient,
    document: dict[str, Any],
    identities: list[UUID],
    integration_engine: AsyncEngine,
) -> None:
    newer = deepcopy(document)
    newer["message_id"] = str(identities[1])
    newer["payload"]["schedule_version"] = 3
    newer["payload"]["participation_no"] = 2
    for item in (newer, document):
        assert (await client.post(PATH, json=item, headers=HEADERS)).status_code == 202
    async with integration_engine.connect() as connection:
        rows = (
            await connection.scalars(
                select(NotificationJob.payload).where(NotificationJob.id.in_(identities))
            )
        ).all()
        assert {row["payload"]["schedule_version"] for row in rows} == {1, 3}


async def test_lost_response_after_commit_and_new_service_instance(
    document: dict[str, Any], integration_engine: AsyncEngine
) -> None:
    app = create_app(settings_for(integration_engine))
    transport = httpx.ASGITransport(app=app)

    class LoseResponse(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            response = await transport.handle_async_request(request)
            assert response.status_code == 202
            await response.aclose()
            raise httpx.ReadTimeout("response lost after commit", request=request)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=LoseResponse(), base_url="http://notifications") as client,
    ):
        with pytest.raises(httpx.ReadTimeout):
            await client.post(PATH, json=document, headers=HEADERS)
    # The old application's pool is disposed. Only the database survives.
    restarted = create_app(settings_for(integration_engine))
    async with (
        restarted.router.lifespan_context(restarted),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=restarted), base_url="http://notifications"
        ) as client,
    ):
        assert (await client.post(PATH, json=document, headers=HEADERS)).status_code == 202
    async with integration_engine.connect() as connection:
        assert (
            len(
                (
                    await connection.scalars(
                        select(NotificationJob.id).where(
                            NotificationJob.id == UUID(document["message_id"])
                        )
                    )
                ).all()
            )
            == 1
        )
