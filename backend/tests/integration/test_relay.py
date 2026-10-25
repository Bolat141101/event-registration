import asyncio
import json
from datetime import timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import EmailOutbox, NotificationKind, OutboxStatus
from app.notifications.relay import Relay
from tests.integration.business_support import Business

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
TOKEN = "test_notifications_internal_token_32_characters_minimum"


@pytest.fixture
def relay_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "notifications_internal_token": SecretStr(TOKEN),
            "relay_max_attempts": 3,
            "relay_backoff_base": 1.0,
            "relay_backoff_cap": 2.0,
        }
    )


def accepted(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        202, json={"message_id": json.loads(request.content)["message_id"], "status": "accepted"}
    )


async def first_ticket(business: Business) -> EmailOutbox:
    event = await business.create()
    person = await business.join(event.id, "relay@example.test")
    return next(m for m in await business.messages(person) if m.kind == NotificationKind.TICKET)


async def stored(business: Business, identity: UUID) -> EmailOutbox:
    async with AsyncSession(business.engine, expire_on_commit=False) as session:
        message = await session.get(EmailOutbox, identity)
        assert message is not None
        return message


async def test_http_acceptance_is_forwarded_not_sent_without_open_transaction(
    business: Business, relay_settings: Settings
) -> None:
    message = await first_ticket(business)

    async def receive(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        async with business.engine.begin() as connection:
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                        "AND usename=current_user AND state LIKE 'idle in transaction%'"
                    )
                )
                == 0
            )
            # Also prove the business event lock is free during HTTP.
            await connection.execute(text("SELECT id FROM events FOR UPDATE NOWAIT"))
        assert (await stored(business, message.id)).prepared_at is not None
        return accepted(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        assert await relay.run_once()
        assert not await relay.run_once()
    result = await stored(business, message.id)
    assert result.status == OutboxStatus.FORWARDED
    assert result.attempts == 1 and result.last_error is None
    assert result.payload["message_id"] == str(message.id)


@pytest.mark.parametrize("failure", ["connect", "timeout", 503, 429, 408])
async def test_unavailable_recipient_has_persisted_bounded_backoff(
    business: Business, relay_settings: Settings, failure: str | int
) -> None:
    message = await first_ticket(business)
    bodies: list[bytes] = []

    def receive(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        if failure == "connect":
            raise httpx.ConnectError("private details", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private details", request=request)
        return httpx.Response(int(failure))

    for attempt, delay in [(1, 1), (2, 2), (3, 2)]:
        # New client and relay per attempt simulate restart with no in-memory retry state.
        async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
            relay = Relay(
                async_sessionmaker(business.engine, expire_on_commit=False),
                client,
                relay_settings,
                business.clock,
            )
            assert await relay.run_once()
            result = await stored(business, message.id)
            assert result.attempts == attempt
            assert result.available_at == business.clock() + timedelta(seconds=delay)
            assert "private details" not in (result.last_error or "")
            assert not await relay.run_once()
        business.clock.now += timedelta(seconds=delay)
    assert (await stored(business, message.id)).status == OutboxStatus.FAILED
    assert len(bodies) == 3 and len(set(bodies)) == 1


@pytest.mark.parametrize("status", [401, 409, 422, 301, 200])
async def test_permanent_or_protocol_error_keeps_failed_job(
    business: Business, relay_settings: Settings, status: int
) -> None:
    message = await first_ticket(business)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(status))
    ) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        assert await relay.run_once()
        assert not await relay.run_once()
    result = await stored(business, message.id)
    assert result.status == OutboxStatus.FAILED and result.attempts == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": "sent"},
        {"message_id": "00000000-0000-0000-0000-000000000000", "status": "accepted"},
    ],
)
async def test_invalid_ack_never_marks_forwarded(
    business: Business, relay_settings: Settings, body: dict[str, Any]
) -> None:
    message = await first_ticket(business)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(202, json=body))
    ) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        await relay.run_once()
    assert (await stored(business, message.id)).status == OutboxStatus.PENDING


async def test_receiver_committed_but_core_ack_update_crashed_then_restarts(
    business: Business, relay_settings: Settings
) -> None:
    message = await first_ticket(business)
    bodies: list[bytes] = []

    def receive(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return accepted(request)

    sessions = async_sessionmaker(business.engine, expire_on_commit=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        relay = Relay(sessions, client, relay_settings, business.clock)
        with (
            patch.object(relay, "finish", side_effect=RuntimeError("crash after accepted")),
            pytest.raises(RuntimeError, match="crash"),
        ):
            await relay.run_once()
    assert (await stored(business, message.id)).status == OutboxStatus.PENDING
    business.clock.now += timedelta(seconds=1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        assert await Relay(sessions, client, relay_settings, business.clock).run_once()
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    assert (await stored(business, message.id)).status == OutboxStatus.FORWARDED


async def test_prepared_retry_preserves_snapshot_after_cancel_resume_and_reschedule(
    business: Business, relay_settings: Settings
) -> None:
    event = await business.create()
    person = await business.join(event.id, "immutable@example.test")
    message = next(m for m in await business.messages(person) if m.kind == NotificationKind.TICKET)
    bodies: list[bytes] = []

    def receive(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(503) if len(bodies) == 1 else accepted(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        await relay.run_once()
        await business.cancel(person)
        await business.resume(person)
        await business.schedule(event.id, business.clock() + timedelta(days=3), 1)
        business.clock.now += timedelta(seconds=1)
        # New participation jobs can precede the retry. Drain due jobs only.
        while await relay.run_once():
            pass
    retries = [body for body in bodies if json.loads(body)["message_id"] == str(message.id)]
    assert len(retries) == 2 and retries[0] == retries[1]
    assert json.loads(retries[-1])["payload"]["participation_no"] == 1


@pytest.mark.parametrize("case", ["cancelled", "generation", "expired", "early"])
async def test_unprepared_job_rechecked_under_event_lock(
    business: Business, relay_settings: Settings, case: str
) -> None:
    event = await business.create()
    person = await business.join(event.id, "stale@example.test")
    message = next(
        m for m in await business.messages(person) if m.kind == NotificationKind.REMINDER
    )
    async with AsyncSession(business.engine) as session, session.begin():
        row = await session.get(EmailOutbox, message.id)
        assert row is not None
        row.available_at = business.clock()
        if case == "generation":
            row.payload = {**row.payload, "participation_no": 99}
    if case == "cancelled":
        await business.cancel(person)
    if case == "expired":
        business.clock.now = event.starts_at
    async with httpx.AsyncClient(transport=httpx.MockTransport(accepted)) as client:
        relay = Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            relay_settings,
            business.clock,
        )
        assert await relay.prepare(message.id) is None
    result = await stored(business, message.id)
    assert result.prepared_at is None and result.attempts == 0
    if case == "early":
        assert result.status == OutboxStatus.PENDING
        assert result.available_at == event.starts_at - timedelta(hours=24)
    else:
        assert result.status == OutboxStatus.CANCELLED


async def test_overall_http_deadline_keeps_pending_retry(
    business: Business, relay_settings: Settings
) -> None:
    message = await first_ticket(business)

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return accepted(request)

    limited = relay_settings.model_copy(update={"relay_timeout": 0.01})
    async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
        await Relay(
            async_sessionmaker(business.engine, expire_on_commit=False),
            client,
            limited,
            business.clock,
        ).run_once()
    row = await stored(business, message.id)
    assert row.status == OutboxStatus.PENDING and row.attempts == 1
    assert row.last_error == "Notifications transport error: TimeoutError"


async def test_restart_after_prepare_before_http_recovers_same_command(
    business: Business, relay_settings: Settings
) -> None:
    message = await first_ticket(business)
    sessions = async_sessionmaker(business.engine, expire_on_commit=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(accepted)) as client:
        prepared = await Relay(sessions, client, relay_settings, business.clock).prepare(message.id)
    assert prepared is not None
    row = await stored(business, message.id)
    assert row.attempts == 1 and row.status == OutboxStatus.PENDING
    business.clock.now += timedelta(seconds=1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(accepted)) as client:
        await Relay(sessions, client, relay_settings, business.clock).run_once()
    row = await stored(business, message.id)
    assert row.attempts == 2 and row.status == OutboxStatus.FORWARDED
    assert row.payload == prepared.model_dump(mode="json")


async def test_two_relays_cannot_forward_same_prepared_job_while_first_http_is_pending(
    business: Business, relay_settings: Settings
) -> None:
    await first_ticket(business)
    entered, release = asyncio.Event(), asyncio.Event()
    received: list[bytes] = []

    async def receive(request: httpx.Request) -> httpx.Response:
        received.append(request.content)
        entered.set()
        await release.wait()
        return accepted(request)

    sessions = async_sessionmaker(business.engine, expire_on_commit=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        first = asyncio.create_task(
            Relay(sessions, client, relay_settings, business.clock).run_once()
        )
        await asyncio.wait_for(entered.wait(), 3)
        business.clock.now += timedelta(seconds=10)
        try:
            assert not await Relay(sessions, client, relay_settings, business.clock).run_once()
        finally:
            release.set()
            assert await first
    assert len(received) == 1


async def test_operator_retry_and_queue_diagnostics_preserve_frozen_payload(
    business: Business, relay_settings: Settings
) -> None:
    from app.notifications.retry import retry_failed
    from app.operations import summary

    message = await first_ticket(business)
    sessions = async_sessionmaker(business.engine, expire_on_commit=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(accepted)) as client:
        relay = Relay(sessions, client, relay_settings, business.clock)
        assert await relay.prepare(message.id)
    async with sessions() as session, session.begin():
        item = await session.get(EmailOutbox, message.id)
        assert item
        frozen, boundary = item.payload, item.prepared_at
        item.status = OutboxStatus.FAILED
    report = await summary()
    failed_sample = report["failed_ids_sample"]
    assert isinstance(failed_sample, list)
    assert str(message.id) in failed_sample
    assert "relay@example.test" not in str(report)
    assert await retry_failed(sessions, message.id, business.clock)
    assert not await retry_failed(sessions, message.id, business.clock)
    item = await stored(business, message.id)
    assert item.payload == frozen and item.prepared_at == boundary and item.attempts == 0
