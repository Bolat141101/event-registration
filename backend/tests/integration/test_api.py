import asyncio
import os
from collections.abc import AsyncIterator
from datetime import timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import EmailOutbox, Event, NotificationKind, OutboxStatus, Registration
from app.main import create_app
from app.services.common import token_hash
from tests.integration.business_support import Business, Participant

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
ORGANIZER = "integration_organizer_secret_32_characters"
AUTH = {"Authorization": f"Bearer {ORGANIZER}"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(business: Business) -> AsyncIterator[AsyncClient]:
    settings = Settings(database_url=os.environ["TEST_DATABASE_URL"], organizer_token=ORGANIZER)
    app = create_app(settings, clock=business.clock)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http


async def test_create_list_detail_and_aggregate_snapshots(
    client: AsyncClient, business: Business
) -> None:
    response = await client.post(
        "/api/events",
        headers=AUTH,
        json={
            "description": "  Встреча  ",
            "starts_at": (business.clock() + timedelta(days=2)).isoformat(),
            "capacity": 2,
        },
    )
    assert response.status_code == 201
    event_id = UUID(response.json()["id"])
    business.event_ids.append(event_id)
    assert response.json()["description"] == "Встреча"
    assert response.json()["confirmed"] == response.json()["checked_in"] == 0
    people = [(await business.join(event_id, f"person{i}@example.test")) for i in range(3)]
    details = (await client.get(f"/api/events/{event_id}")).json()
    assert (details["confirmed"], details["waitlisted"], details["checked_in"]) == (2, 1, 0)
    assert details in (await client.get("/api/events")).json()
    assert ORGANIZER not in str(details)
    assert all(person.token not in str(details) for person in people)
    assert "email" not in details and "ticket_code" not in details
    assert (await client.get(f"/api/events/{uuid4()}")).status_code == 404


@pytest.mark.parametrize("operation", ["create", "schedule", "checkin"])
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong-organizer"}])
async def test_organizer_required_for_every_mutation(
    client: AsyncClient, business: Business, operation: str, headers: dict[str, str]
) -> None:
    event = await business.create()
    method, path, body = {
        "create": (
            "POST",
            "/api/events",
            {
                "description": "Встреча",
                "starts_at": event.starts_at.isoformat(),
                "capacity": 1,
            },
        ),
        "schedule": (
            "PATCH",
            f"/api/events/{event.id}/schedule",
            {
                "starts_at": (event.starts_at + timedelta(days=1)).isoformat(),
                "expected_schedule_version": 1,
            },
        ),
        "checkin": ("POST", f"/api/events/{event.id}/check-ins", {"ticket_code": "ticket"}),
    }[operation]
    response = await client.request(method, path, headers=headers, json=body)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert ORGANIZER not in response.text
    assert "wrong-organizer" not in response.text


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/registration", "GET"),
        ("/api/registration/cancel", "POST"),
        ("/api/registration/resume", "POST"),
    ],
)
@pytest.mark.parametrize("token", [None, "invalid-participant", ORGANIZER, "user@example.test"])
async def test_private_routes_reject_missing_and_wrong_tokens(
    client: AsyncClient, path: str, method: str, token: str | None
) -> None:
    response = await client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {token}"} if token else {},
        **({"json": {"expected_participation_no": 1}} if method == "POST" else {}),
    )
    assert response.status_code == 401
    if token:
        assert token not in response.text


async def test_public_registration_privacy_and_private_cancel_resume(
    client: AsyncClient, business: Business, caplog: pytest.LogCaptureFixture
) -> None:
    event = await business.create()
    response = await client.post(
        f"/api/events/{event.id}/registrations", json={"email": " USER@example.test "}
    )
    assert response.status_code == 202
    neutral = response.json()
    assert set(neutral) == {"message"}
    async with AsyncSession(business.engine, expire_on_commit=False) as session:
        # Read only: a service call here could create data the HTTP request failed to write.
        entry = (
            await session.scalars(select(Registration).where(Registration.event_id == event.id))
        ).one()
        messages = (
            await session.scalars(
                select(EmailOutbox).where(EmailOutbox.registration_id == entry.id)
            )
        ).all()
        assert len(messages) == 2
        by_kind = {message.kind: message for message in messages}
        assert set(by_kind) == {NotificationKind.TICKET, NotificationKind.REMINDER}
        assert all(message.status == OutboxStatus.PENDING for message in messages)
        ticket = by_kind[NotificationKind.TICKET]
        reminder = by_kind[NotificationKind.REMINDER]
        assert ticket.dedup_key == f"ticket:{entry.id}:1"
        assert reminder.dedup_key == f"reminder:{entry.id}"
        assert ticket.payload["ticket_code"] == entry.ticket_code
        assert entry.ticket_code is not None
        assert entry.status == "confirmed" and entry.participation_no == 1
        assert entry.waitlist_seq is None and entry.checked_in_at is None
        assert all(message.payload["recipient"] == "user@example.test" for message in messages)
        assert "manage_path" not in reminder.payload
        person = Participant(entry.id, ticket.payload["manage_path"].split("#token=", 1)[1])
        assert entry.manage_token_hash == token_hash(person.token)
        assert entry.email == "user@example.test"
        assert entry.manage_token_hash != person.token
    headers = {"Authorization": f"Bearer {person.token}"}
    private = await client.get("/api/registration", headers=headers)
    assert private.status_code == 200 and private.json()["ticket_code"]
    assert private.json()["ticket_code"] == entry.ticket_code
    assert person.token not in private.text and "manage_token_hash" not in private.text
    cancelled = await client.post(
        "/api/registration/cancel", headers=headers, json={"expected_participation_no": 1}
    )
    assert cancelled.status_code == 200 and cancelled.json()["ticket_code"] is None
    repeat = await client.post(
        f"/api/events/{event.id}/registrations", json={"email": "user@example.test"}
    )
    assert repeat.json() == neutral
    assert (await business.private(person)).status == "cancelled"
    resumed = await client.post(
        "/api/registration/resume", headers=headers, json={"expected_participation_no": 1}
    )
    assert resumed.status_code == 200 and resumed.json()["participation_no"] == 2
    assert resumed.json()["ticket_code"] != private.json()["ticket_code"]
    stale = await client.post(
        "/api/registration/cancel", headers=headers, json={"expected_participation_no": 1}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "participation_conflict"
    assert person.token not in caplog.text and ORGANIZER not in caplog.text
    assert person.token not in response.text


@pytest.mark.parametrize("ticket_code", ["\x00", "before\x00after", "\x00ticket\x00"])
async def test_checkin_rejects_null_character_without_changing_registration(
    client: AsyncClient, business: Business, ticket_code: str
) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    before = await business.private(person)
    business.clock.now = event.starts_at
    response = await client.post(
        f"/api/events/{event.id}/check-ins",
        headers=AUTH,
        json={"ticket_code": ticket_code},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["errors"][0]["loc"] == ["body", "ticket_code"]
    assert (await business.private(person)) == before
    assert (await business.event(event.id)).checked_in == 0


async def test_schedule_and_checkin_http_statuses(client: AsyncClient, business: Business) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    ticket = (await business.private(person)).ticket_code
    body = {
        "starts_at": (event.starts_at + timedelta(hours=1)).isoformat(),
        "expected_schedule_version": 1,
    }
    response = await client.patch(f"/api/events/{event.id}/schedule", json=body, headers=AUTH)
    assert response.status_code == 200 and response.json()["schedule_version"] == 2
    assert (
        await client.patch(f"/api/events/{event.id}/schedule", json=body, headers=AUTH)
    ).json() == response.json()
    body["starts_at"] = (event.starts_at + timedelta(hours=2)).isoformat()
    assert (
        await client.patch(f"/api/events/{event.id}/schedule", json=body, headers=AUTH)
    ).status_code == 409
    checkin_path = f"/api/events/{event.id}/check-ins"
    assert (
        await client.post(checkin_path, json={"ticket_code": ticket}, headers=AUTH)
    ).status_code == 409
    business.clock.now = event.starts_at + timedelta(hours=1)
    assert (
        await client.post(checkin_path, json={"ticket_code": "bad-ticket"}, headers=AUTH)
    ).status_code == 404
    assert (
        await client.post(checkin_path, json={"ticket_code": ticket}, headers=AUTH)
    ).status_code == 200
    assert (
        await client.post(checkin_path, json={"ticket_code": ticket}, headers=AUTH)
    ).status_code == 409
    assert (await client.get(f"/api/events/{event.id}")).json()["checked_in"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"capacity": 0},
        {"capacity": -1},
        {"capacity": True},
        {"capacity": 2_147_483_648},
        {"description": "   "},
        {"starts_at": "2030-02-01T10:00:00"},
        {"unknown": "secret-value"},
    ],
)
async def test_event_validation_does_not_echo_input(
    client: AsyncClient, business: Business, changes: dict[str, object]
) -> None:
    body = {
        "description": "Встреча",
        "capacity": 1,
        "starts_at": (business.clock() + timedelta(days=1)).isoformat(),
        **changes,
    }
    response = await client.post("/api/events", json=body, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert "secret-value" not in response.text


@pytest.mark.parametrize(
    "starts_at",
    ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"],
)
async def test_create_rejects_dates_outside_utc_range_before_service(
    client: AsyncClient, starts_at: str
) -> None:
    with patch("app.api.events.events.create_event") as create:
        response = await client.post(
            "/api/events",
            headers=AUTH,
            json={"description": "Встреча", "capacity": 1, "starts_at": starts_at},
        )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["errors"][0]["loc"] == ["body", "starts_at"]
    create.assert_not_called()


@pytest.mark.parametrize(
    "starts_at",
    ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"],
)
async def test_reschedule_rejects_dates_outside_utc_range_without_changes(
    client: AsyncClient, business: Business, starts_at: str
) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    before = await business.event(event.id)
    messages = [
        (m.id, m.payload, m.available_at, m.status) for m in (await business.messages(person))
    ]
    with patch("app.api.events.events.reschedule_event") as reschedule:
        response = await client.patch(
            f"/api/events/{event.id}/schedule",
            headers=AUTH,
            json={"starts_at": starts_at, "expected_schedule_version": 1},
        )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["errors"][0]["loc"] == ["body", "starts_at"]
    reschedule.assert_not_called()
    assert (await business.event(event.id)) == before
    assert [
        (m.id, m.payload, m.available_at, m.status) for m in (await business.messages(person))
    ] == messages


@pytest.mark.parametrize("description", ["\x00", "До\x00после", "\x00Встреча\x00"])
async def test_description_rejects_null_character_before_service(
    client: AsyncClient, business: Business, description: str
) -> None:
    with patch("app.api.events.events.create_event") as create:
        response = await client.post(
            "/api/events",
            headers=AUTH,
            json={
                "description": description,
                "capacity": 1,
                "starts_at": (business.clock() + timedelta(days=1)).isoformat(),
            },
        )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["errors"][0]["loc"] == ["body", "description"]
    create.assert_not_called()


@pytest.mark.parametrize("email", ["bad", "a..b@example.test", "a@bad", "a@-example.test"])
async def test_email_validation(client: AsyncClient, business: Business, email: str) -> None:
    event = await business.create()
    response = await client.post(f"/api/events/{event.id}/registrations", json={"email": email})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_email"
    assert (await business.event(event.id)).confirmed == 0


async def test_capacity_is_not_editable(client: AsyncClient, business: Business) -> None:
    event = await business.create()
    response = await client.patch(
        f"/api/events/{event.id}/schedule",
        headers=AUTH,
        json={
            "starts_at": (event.starts_at + timedelta(days=1)).isoformat(),
            "expected_schedule_version": 1,
            "capacity": 100,
        },
    )
    assert response.status_code == 422
    assert (await business.event(event.id)).capacity == 1


async def test_closed_registration_does_not_disclose_whether_email_exists(
    client: AsyncClient, business: Business
) -> None:
    event = await business.create()
    person = await business.join(event.id, "existing@example.test")
    original = [(m.id, m.payload, m.status) for m in (await business.messages(person))]
    business.clock.now = event.starts_at
    responses = [
        await client.post(f"/api/events/{event.id}/registrations", json={"email": email})
        for email in ("existing@example.test", "new@example.test")
    ]
    assert [response.status_code for response in responses] == [202, 202]
    assert responses[0].json() == responses[1].json()
    async with AsyncSession(business.engine, expire_on_commit=False) as session:
        assert (
            await session.scalar(
                select(Registration.id).where(Registration.email == "new@example.test")
            )
        ) is None
    assert (await business.event(event.id)).confirmed == 1
    assert [(m.id, m.payload, m.status) for m in (await business.messages(person))] == original


async def test_real_lock_timeout_returns_503_and_rolls_back(
    client: AsyncClient, business: Business
) -> None:
    event = await business.create()
    async with AsyncSession(business.engine, expire_on_commit=False) as blocker, blocker.begin():
        await blocker.execute(select(Event.id).where(Event.id == event.id).with_for_update())
        response = await client.post(
            f"/api/events/{event.id}/registrations", json={"email": "user@example.test"}
        )
        assert response.status_code == 503
        assert response.json()["code"] == "database_unavailable"
    assert (await business.event(event.id)).confirmed == 0
    response = await client.post(
        f"/api/events/{event.id}/registrations", json={"email": "user@example.test"}
    )
    assert response.status_code == 202 and (await business.event(event.id)).confirmed == 1


async def test_database_errors_do_not_expose_secrets(
    client: AsyncClient, business: Business, caplog: pytest.LogCaptureFixture
) -> None:
    event = await business.create()
    error = OperationalError(
        "SQL private-token", {"password": "private-password"}, Exception("private-password")
    )
    with patch("app.api.events.registrations.register", side_effect=error):
        response = await client.post(
            f"/api/events/{event.id}/registrations", json={"email": "user@example.test"}
        )
    assert response.status_code == 503
    assert "private-password" not in response.text + caplog.text
    assert "private-token" not in response.text + caplog.text


async def test_openapi_exposes_new_routes(client: AsyncClient) -> None:
    response = await client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "post" in paths["/api/events"]
    assert "patch" in paths["/api/events/{event_id}/schedule"]
    assert "/api/registration/resume" in paths
    assert "get" in paths["/api/events/{event_id}/stream"]
    assert "get" in paths["/api/organizer/access"]


async def test_waiting_for_event_lock_does_not_block_other_requests(
    client: AsyncClient, business: Business
) -> None:
    event = await business.create()
    async with (
        asyncio.TaskGroup() as group,
        AsyncSession(business.engine) as blocker,
        blocker.begin(),
    ):
        await blocker.execute(select(Event.id).where(Event.id == event.id).with_for_update())
        task = group.create_task(
            client.post(
                f"/api/events/{event.id}/registrations", json={"email": "waiting@example.test"}
            )
        )
        # Observe the real server-side wait before probing unrelated requests.
        async with business.engine.connect() as observer, asyncio.timeout(1.5):
            while not await observer.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "AND cardinality(pg_blocking_pids(pid)) > 0)"
                )
            ):
                await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                await asyncio.sleep(0.01)
            async with asyncio.timeout(1):
                health = await client.get("/api/health")
                detail = await client.get(f"/api/events/{event.id}")
            assert health.status_code == detail.status_code == 200
            assert detail.json()["confirmed"] == 0
            assert not task.done()
    assert task.result().status_code == 202
    assert (await business.event(event.id)).confirmed == 1


@pytest.mark.parametrize("error", [TimeoutError("private timeout"), OSError("private connection")])
async def test_async_driver_connection_errors_return_503(
    client: AsyncClient, business: Business, error: OSError, caplog: pytest.LogCaptureFixture
) -> None:
    event = await business.create()
    with patch("app.api.events.registrations.register", side_effect=error):
        response = await client.post(
            f"/api/events/{event.id}/registrations", json={"email": "user@example.test"}
        )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert response.json()["code"] == "database_unavailable"
    assert str(error) not in response.text + caplog.text
