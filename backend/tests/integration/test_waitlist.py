"""Verify queue allocation/storage, not the still unimplemented registration API."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadEvent
from time import monotonic, sleep
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.orm import Session

from app.db.models import Event, Registration, RegistrationStatus
from app.db.waitlist import next_waitlist_seq

pytestmark = pytest.mark.integration


@pytest.fixture
def committed_event(integration_engine: Engine) -> Iterator[UUID]:
    with Session(integration_engine) as session, session.begin():
        item = Event(
            description="Проверка очереди",
            starts_at=datetime.now(UTC) + timedelta(days=2),
            capacity=1,
        )
        session.add(item)
        session.flush()
        event_id = item.id
    try:
        yield event_id
    finally:
        with integration_engine.begin() as connection:
            connection.execute(delete(Registration).where(Registration.event_id == event_id))
            connection.execute(delete(Event).where(Event.id == event_id))


def enqueue(session: Session, event_id: UUID) -> Registration:
    position = next_waitlist_seq(session, event_id)
    entry = Registration(
        event_id=event_id,
        email=f"{uuid4().hex}@example.test",
        status=RegistrationStatus.WAITLISTED,
        waitlist_seq=position,
        manage_token_hash=uuid4().hex,
    )
    session.add(entry)
    session.flush()
    return entry


def test_allocation_requires_caller_transaction(integration_engine: Engine) -> None:
    with (
        Session(integration_engine) as session,
        pytest.raises(RuntimeError, match="explicit caller transaction"),
    ):
        next_waitlist_seq(session, uuid4())


def test_allocation_rejects_unknown_event(integration_engine: Engine) -> None:
    with (
        Session(integration_engine) as session,
        session.begin(),
        pytest.raises(LookupError, match="does not exist"),
    ):
        next_waitlist_seq(session, uuid4())


def test_fifo_tail_reuse_after_cancel_and_promotion(
    integration_engine: Engine, committed_event: UUID
) -> None:
    with Session(integration_engine) as session, session.begin():
        first = enqueue(session, committed_event)
        second = enqueue(session, committed_event)
        third = enqueue(session, committed_event)
        assert [first.waitlist_seq, second.waitlist_seq, third.waitlist_seq] == [1, 2, 3]
        # Storage transitions only; automatic promotion is not implemented yet.
        third.status = RegistrationStatus.CANCELLED
        third.waitlist_seq = None
        session.flush()
        replacement = enqueue(session, committed_event)
        assert replacement.waitlist_seq == 3
        ordered = session.scalars(
            select(Registration)
            .where(
                Registration.event_id == committed_event,
                Registration.status == RegistrationStatus.WAITLISTED,
            )
            .order_by(Registration.waitlist_seq)
        ).all()
        assert [entry.id for entry in ordered] == [first.id, second.id, replacement.id]
        first.status = RegistrationStatus.CONFIRMED
        first.ticket_code = uuid4().hex
        first.waitlist_seq = None
        session.flush()
        assert next_waitlist_seq(session, committed_event) == 4
        for entry in (second, replacement):
            entry.status = RegistrationStatus.CANCELLED
            entry.waitlist_seq = None
        session.flush()
        assert next_waitlist_seq(session, committed_event) == 1


def test_rollback_does_not_reserve_queue_position(
    integration_engine: Engine, committed_event: UUID
) -> None:
    with Session(integration_engine) as session:
        with pytest.raises(RuntimeError, match="abort"), session.begin():
            assert enqueue(session, committed_event).waitlist_seq == 1
            raise RuntimeError("abort")
        with session.begin():
            assert enqueue(session, committed_event).waitlist_seq == 1


def test_concurrent_allocation_waits_for_event_lock_and_reads_committed_max(
    integration_engine: Engine, committed_event: UUID
) -> None:
    second_started = ThreadEvent()
    second_pid: list[int] = []

    def second_transaction() -> int | None:
        with Session(integration_engine) as session, session.begin():
            second_pid.append(session.execute(text("SELECT pg_backend_pid()")).scalar_one())
            second_started.set()
            return enqueue(session, committed_event).waitlist_seq

    # Separate connections/transactions with actual commits; no shared Session or mock lock.
    with ThreadPoolExecutor(max_workers=1) as executor, Session(integration_engine) as first:
        try:
            with first.begin():
                assert enqueue(first, committed_event).waitlist_seq == 1
                first_pid = first.execute(text("SELECT pg_backend_pid()")).scalar_one()
                future = executor.submit(second_transaction)
                assert second_started.wait(timeout=5)
                deadline = monotonic() + 5
                with integration_engine.connect() as observer:
                    while monotonic() < deadline:
                        blockers = observer.execute(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": second_pid[0]}
                        ).scalar_one()
                        if first_pid in blockers:
                            break
                        sleep(0.01)
                    else:
                        pytest.fail("The second transaction did not wait for the event lock")
                assert not future.done()
            assert future.result(timeout=5) == 2
        finally:
            first.rollback()
    with Session(integration_engine) as session:
        positions = session.scalars(
            select(Registration.waitlist_seq)
            .where(Registration.event_id == committed_event)
            .order_by(Registration.waitlist_seq)
        ).all()
        assert positions == [1, 2]
