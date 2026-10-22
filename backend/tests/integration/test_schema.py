from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.health import database_is_ready, expected_schema_heads
from app.db.models import (
    EmailOutbox,
    Event,
    NotificationKind,
    OutboxStatus,
    Registration,
    RegistrationStatus,
)

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def event(session: AsyncSession, capacity: int = 1) -> Event:
    item = Event(
        description="Описание события",
        starts_at=datetime.now(UTC) + timedelta(days=2),
        capacity=capacity,
    )
    session.add(item)
    await session.flush()
    return item


async def registration(
    session: AsyncSession, item: Event, email: str = "user@example.test"
) -> Registration:
    entry = Registration(
        event_id=item.id,
        email=email,
        status=RegistrationStatus.CONFIRMED,
        ticket_code=uuid4().hex,
        manage_token_hash=uuid4().hex,
    )
    session.add(entry)
    await session.flush()
    return entry


async def test_migrated_database_is_ready(integration_engine: AsyncEngine) -> None:
    assert await database_is_ready(integration_engine, expected_schema_heads())


async def test_database_isolation_and_timezone(integration_engine: AsyncEngine) -> None:
    async with integration_engine.connect() as connection:
        assert (
            await connection.execute(text("SHOW transaction_isolation"))
        ).scalar_one() == "read committed"
        timestamp = (await connection.execute(text("SELECT now()"))).scalar_one()
        assert timestamp.tzinfo is not None


async def test_defaults_and_timezone_round_trip(db_session: AsyncSession) -> None:
    item = await event(db_session)
    entry = await registration(db_session, item)
    await db_session.refresh(item)
    assert item.schedule_version == 1
    assert item.starts_at.utcoffset() == timedelta(0)
    assert entry.participation_no == 1


@pytest.mark.parametrize("capacity", [0, -1])
async def test_capacity_must_be_positive(db_session: AsyncSession, capacity: int) -> None:
    with pytest.raises(IntegrityError, match="positive_capacity"):
        await event(db_session, capacity)


async def test_event_email_is_unique(db_session: AsyncSession) -> None:
    item = await event(db_session)
    await registration(db_session, item, "user@example.test")
    with pytest.raises(IntegrityError, match="uq_registrations_event_email"):
        await registration(db_session, item, " USER@example.test ")


async def test_same_email_can_register_for_different_events(db_session: AsyncSession) -> None:
    await registration(db_session, (await event(db_session)))
    await registration(db_session, (await event(db_session)))


async def test_email_normalization_is_enforced(db_session: AsyncSession) -> None:
    entry = await registration(db_session, (await event(db_session)))
    # Raw SQL must not bypass the canonical-storage constraint.
    with pytest.raises(IntegrityError, match="normalized_email"):
        (
            await db_session.execute(
                text("UPDATE registrations SET email = 'UPPER@example.test' WHERE id = :id"),
                {"id": entry.id},
            )
        )


async def test_orm_normalizes_email_on_insert_and_update(db_session: AsyncSession) -> None:
    entry = await registration(db_session, (await event(db_session)), " USER@example.test ")
    await db_session.refresh(entry)
    assert entry.email == "user@example.test"
    entry.email = " Other@EXAMPLE.test "
    await db_session.flush()
    await db_session.refresh(entry)
    assert entry.email == "other@example.test"


@pytest.mark.parametrize(
    "state,position,ticket,checked_in",
    [
        ("waitlisted", None, None, None),
        ("waitlisted", 0, None, None),
        ("waitlisted", 1, "invalid-ticket", None),
        ("waitlisted", 1, None, datetime.now(UTC)),
        ("confirmed", None, None, None),
        ("confirmed", 1, "ticket", None),
        ("cancelled", 1, None, None),
        ("cancelled", None, "old-ticket", None),
        ("cancelled", None, None, datetime.now(UTC)),
    ],
)
async def test_inconsistent_registration_state_is_rejected(
    db_session: AsyncSession,
    state: str,
    position: int | None,
    ticket: str | None,
    checked_in: datetime | None,
) -> None:
    item = await event(db_session)
    with pytest.raises(IntegrityError, match="consistent_state"):
        (
            await db_session.execute(
                text(
                    "INSERT INTO registrations "
                    "(event_id, email, status, waitlist_seq, ticket_code, "
                    "manage_token_hash, checked_in_at) "
                    "VALUES (:event_id, 'user@example.test', :status, "
                    ":position, :ticket, :hash, :checked_in)"
                ),
                {
                    "event_id": item.id,
                    "status": state,
                    "position": position,
                    "ticket": ticket,
                    "hash": uuid4().hex,
                    "checked_in": checked_in,
                },
            )
        )


async def test_waitlist_position_is_unique_per_event(db_session: AsyncSession) -> None:
    item = await event(db_session)
    entry = await registration(db_session, item)
    entry.status = RegistrationStatus.WAITLISTED
    entry.waitlist_seq = 1
    entry.ticket_code = None
    await db_session.flush()
    second = await registration(db_session, item, "other@example.test")
    second.status = RegistrationStatus.WAITLISTED
    second.waitlist_seq = 1
    second.ticket_code = None
    with pytest.raises(IntegrityError, match="uq_registrations_event_waitlist_seq"):
        await db_session.flush()


async def test_registration_and_outbox_rollback_together(db_session: AsyncSession) -> None:
    item = await event(db_session)
    with pytest.raises(RuntimeError, match="simulated failure"):
        async with db_session.begin_nested():
            entry = await registration(db_session, item)
            db_session.add(
                EmailOutbox(
                    registration_id=entry.id,
                    kind=NotificationKind.TICKET,
                    dedup_key=f"ticket:{entry.id}:1",
                    payload={"participation_no": 1},
                    available_at=datetime.now(UTC),
                )
            )
            await db_session.flush()
            raise RuntimeError("simulated failure")
    assert (await db_session.execute(text("SELECT count(*) FROM registrations"))).scalar_one() == 0
    assert (await db_session.execute(text("SELECT count(*) FROM email_outbox"))).scalar_one() == 0


async def test_outbox_logical_message_is_unique(db_session: AsyncSession) -> None:
    entry = await registration(db_session, (await event(db_session)))
    for attempt in range(2):
        db_session.add(
            EmailOutbox(
                registration_id=entry.id,
                kind=NotificationKind.REMINDER,
                dedup_key=f"reminder:{entry.id}",
                payload={},
                available_at=datetime.now(UTC),
            )
        )
        if attempt == 0:
            await db_session.flush()
        else:
            with pytest.raises(IntegrityError, match="uq_email_outbox_dedup_key"):
                await db_session.flush()


async def test_sent_outbox_requires_preparation(db_session: AsyncSession) -> None:
    entry = await registration(db_session, (await event(db_session)))
    db_session.add(
        EmailOutbox(
            registration_id=entry.id,
            kind=NotificationKind.TICKET,
            dedup_key=f"ticket:{entry.id}:1",
            payload={},
            available_at=datetime.now(UTC),
            status=OutboxStatus.SENT,
        )
    )
    with pytest.raises(IntegrityError, match="consistent_delivery_state"):
        await db_session.flush()


async def test_prepared_outbox_can_be_sent_without_sent_at(db_session: AsyncSession) -> None:
    entry = await registration(db_session, (await event(db_session)))
    message = EmailOutbox(
        registration_id=entry.id,
        kind=NotificationKind.TICKET,
        dedup_key=f"ticket:{entry.id}:1",
        payload={"participation_no": 1},
        prepared_at=datetime.now(UTC),
        available_at=datetime.now(UTC),
        status=OutboxStatus.SENT,
        attempts=2,
    )
    db_session.add(message)
    await db_session.flush()
    await db_session.refresh(message)
    assert message.status == OutboxStatus.SENT
    assert message.prepared_at is not None
    assert message.attempts == 2


async def test_cancelled_storage_and_new_participation_preserve_identity(
    db_session: AsyncSession,
) -> None:
    entry = await registration(db_session, (await event(db_session)))
    identity, token_hash, old_ticket = entry.id, entry.manage_token_hash, entry.ticket_code
    entry.status = RegistrationStatus.CANCELLED
    entry.ticket_code = None
    await db_session.flush()
    entry.status = RegistrationStatus.CONFIRMED
    entry.participation_no += 1
    entry.ticket_code = uuid4().hex
    await db_session.flush()
    assert entry.id == identity
    assert entry.manage_token_hash == token_hash
    assert entry.ticket_code != old_ticket
    assert entry.participation_no == 2


async def test_cancelled_email_stays_unique(db_session: AsyncSession) -> None:
    item = await event(db_session)
    entry = await registration(db_session, item)
    entry.status = RegistrationStatus.CANCELLED
    entry.ticket_code = None
    await db_session.flush()
    with pytest.raises(IntegrityError, match="uq_registrations_event_email"):
        await registration(db_session, item, " USER@example.test ")


async def test_ticket_code_is_unique(db_session: AsyncSession) -> None:
    item = await event(db_session)
    first = await registration(db_session, item)
    second = await registration(db_session, item, "other@example.test")
    second.ticket_code = first.ticket_code
    with pytest.raises(IntegrityError, match="uq_registrations_ticket_code"):
        await db_session.flush()


async def test_checkin_timestamp_can_be_stored_on_confirmed_only(db_session: AsyncSession) -> None:
    entry = await registration(db_session, (await event(db_session)))
    timestamp = datetime.now(UTC)
    entry.checked_in_at = timestamp
    await db_session.flush()
    await db_session.refresh(entry)
    assert entry.checked_in_at == timestamp
    entry.status = RegistrationStatus.CANCELLED
    entry.ticket_code = None
    with pytest.raises(IntegrityError, match="consistent_state"):
        await db_session.flush()


async def test_schema_has_exactly_24_domain_columns(integration_engine: AsyncEngine) -> None:
    async with integration_engine.connect() as connection:
        counts = dict(
            (
                await connection.execute(
                    text(
                        "SELECT table_name, count(*) FROM information_schema.columns "
                        "WHERE table_schema = 'public' "
                        "AND table_name IN ('events', 'registrations', 'email_outbox') "
                        "GROUP BY table_name"
                    )
                )
            ).all()
        )
    assert counts == {"events": 5, "registrations": 9, "email_outbox": 10}
