from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.health import database_is_ready, expected_schema_heads
from app.db.models import (
    EmailOutbox,
    Event,
    NotificationKind,
    OutboxStatus,
    Registration,
    RegistrationStatus,
)

pytestmark = pytest.mark.integration


def event(session: Session, capacity: int = 1) -> Event:
    item = Event(
        title="Тестовая встреча",
        description="Описание события",
        starts_at=datetime.now(UTC) + timedelta(days=2),
        capacity=capacity,
    )
    session.add(item)
    session.flush()
    return item


def registration(session: Session, item: Event, email: str = "user@example.test") -> Registration:
    entry = Registration(
        event_id=item.id,
        email=email,
        email_normalized=email.strip().lower(),
        status=RegistrationStatus.CONFIRMED,
        ticket_code=uuid4().hex,
        manage_token_hash=uuid4().hex,
    )
    session.add(entry)
    session.flush()
    return entry


def test_migrated_database_is_ready(integration_engine: Engine) -> None:
    assert database_is_ready(integration_engine, expected_schema_heads())


def test_database_isolation_and_timezone(integration_engine: Engine) -> None:
    with integration_engine.connect() as connection:
        assert (
            connection.execute(text("SHOW transaction_isolation")).scalar_one() == "read committed"
        )
        timestamp = connection.execute(text("SELECT now()")).scalar_one()
        assert timestamp.tzinfo is not None


def test_defaults_and_timezone_round_trip(db_session: Session) -> None:
    item = event(db_session)
    entry = registration(db_session, item)
    db_session.refresh(item)
    assert item.schedule_version == 1
    assert item.next_waitlist_seq == 0
    assert item.starts_at.utcoffset() == timedelta(0)
    assert entry.participation_no == 1


@pytest.mark.parametrize("capacity", [0, -1])
def test_capacity_must_be_positive(db_session: Session, capacity: int) -> None:
    with pytest.raises(IntegrityError, match="positive_capacity"):
        event(db_session, capacity)


def test_event_email_is_unique(db_session: Session) -> None:
    item = event(db_session)
    registration(db_session, item, "user@example.test")
    with pytest.raises(IntegrityError, match="uq_registrations_event_email"):
        registration(db_session, item, " USER@example.test ")


def test_same_email_can_register_for_different_events(db_session: Session) -> None:
    registration(db_session, event(db_session))
    registration(db_session, event(db_session))


def test_email_normalization_is_enforced(db_session: Session) -> None:
    entry = registration(db_session, event(db_session))
    entry.email_normalized = "UPPER@example.test"
    with pytest.raises(IntegrityError, match="normalized_email"):
        db_session.flush()


@pytest.mark.parametrize(
    "state,position,ticket,checked_in,cancelled",
    [
        ("waitlisted", None, None, None, None),
        ("waitlisted", 0, None, None, None),
        ("waitlisted", 1, "invalid-ticket", None, None),
        ("waitlisted", 1, None, datetime.now(UTC), None),
        ("confirmed", None, None, None, None),
        ("confirmed", 1, "ticket", None, None),
        ("cancelled", None, None, None, None),
        ("cancelled", None, "old-ticket", None, datetime.now(UTC)),
        ("cancelled", None, None, datetime.now(UTC), datetime.now(UTC)),
    ],
)
def test_inconsistent_registration_state_is_rejected(
    db_session: Session,
    state: str,
    position: int | None,
    ticket: str | None,
    checked_in: datetime | None,
    cancelled: datetime | None,
) -> None:
    item = event(db_session)
    with pytest.raises(IntegrityError, match="consistent_state"):
        db_session.execute(
            text(
                "INSERT INTO registrations "
                "(event_id, email, email_normalized, status, waitlist_seq, ticket_code, "
                "manage_token_hash, checked_in_at, cancelled_at) "
                "VALUES (:event_id, 'user@example.test', 'user@example.test', :status, "
                ":position, :ticket, :hash, :checked_in, :cancelled)"
            ),
            {
                "event_id": item.id,
                "status": state,
                "position": position,
                "ticket": ticket,
                "hash": uuid4().hex,
                "checked_in": checked_in,
                "cancelled": cancelled,
            },
        )


def test_waitlist_position_is_unique_per_event(db_session: Session) -> None:
    item = event(db_session)
    entry = registration(db_session, item)
    entry.status = RegistrationStatus.WAITLISTED
    entry.waitlist_seq = 1
    entry.ticket_code = None
    db_session.flush()
    second = registration(db_session, item, "other@example.test")
    second.status = RegistrationStatus.WAITLISTED
    second.waitlist_seq = 1
    second.ticket_code = None
    with pytest.raises(IntegrityError, match="uq_registrations_event_waitlist_seq"):
        db_session.flush()


def test_registration_and_outbox_rollback_together(db_session: Session) -> None:
    item = event(db_session)
    with pytest.raises(RuntimeError, match="simulated failure"), db_session.begin_nested():
        entry = registration(db_session, item)
        db_session.add(
            EmailOutbox(
                registration_id=entry.id,
                kind=NotificationKind.TICKET,
                dedup_key=f"ticket:{entry.id}:1",
                payload={"participation_no": 1},
                available_at=datetime.now(UTC),
            )
        )
        db_session.flush()
        raise RuntimeError("simulated failure")
    assert db_session.execute(text("SELECT count(*) FROM registrations")).scalar_one() == 0
    assert db_session.execute(text("SELECT count(*) FROM email_outbox")).scalar_one() == 0


def test_outbox_logical_message_is_unique(db_session: Session) -> None:
    entry = registration(db_session, event(db_session))
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
            db_session.flush()
        else:
            with pytest.raises(IntegrityError, match="uq_email_outbox_dedup_key"):
                db_session.flush()


def test_sent_outbox_requires_preparation_and_timestamp(db_session: Session) -> None:
    entry = registration(db_session, event(db_session))
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
        db_session.flush()
