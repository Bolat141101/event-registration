from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EmailOutbox,
    Event,
    NotificationKind,
    OutboxStatus,
    Registration,
)
from app.services import events, registrations
from app.services.errors import Conflict, DomainError, InvalidInput, NotFound
from tests.integration.business_support import Business, Participant, parallel_while_event_locked

pytestmark = pytest.mark.integration


def notice(business: Business, person: Participant, kind: NotificationKind) -> EmailOutbox:
    return next(message for message in business.messages(person) if message.kind == kind)


def test_two_people_concurrently_take_last_place(business: Business) -> None:
    event = business.create()
    people = parallel_while_event_locked(
        business,
        event.id,
        lambda: business.join(event.id, "one@example.test"),
        lambda: business.join(event.id, "two@example.test"),
    )
    assert all(isinstance(person, Participant) for person in people)
    states = [business.private(person) for person in people]
    assert {state.status for state in states} == {"confirmed", "waitlisted"}
    assert sum(state.ticket_code is not None for state in states) == 1
    assert sorted(state.waitlist_seq for state in states if state.waitlist_seq) == [1]
    assert business.event(event.id).confirmed == 1
    assert business.event(event.id).waitlisted == 1
    assert all(len(business.messages(person)) == 2 for person in people)


def test_same_normalized_email_concurrently_is_one_registration(business: Business) -> None:
    event = business.create()
    people = parallel_while_event_locked(
        business,
        event.id,
        lambda: business.join(event.id, " User@EXAMPLE.test "),
        lambda: business.join(event.id, "user@example.test"),
    )
    assert people[0] == people[1]
    assert len(business.messages(people[0])) == 2
    assert business.event(event.id).confirmed == 1
    assert business.event(event.id).waitlisted == 0


def test_email_in_different_events_and_plus_dot_are_preserved(business: Business) -> None:
    first, second = business.create(3), business.create()
    people = [
        business.join(first.id, value)
        for value in ("Some.One+tag@example.test", "some.one@example.test", "someone@example.test")
    ]
    other = business.join(second.id, "Some.One+tag@example.test")
    assert len({person.id for person in [*people, other]}) == 4
    with Session(business.engine) as session:
        assert session.get(Registration, people[0].id).email == "some.one+tag@example.test"


def test_fifo_abc_promotion_works_without_worker(business: Business) -> None:
    event = business.create()
    owner, a, b, c = [business.join(event.id, f"{name}@example.test") for name in "oabc"]
    assert [business.private(person).waitlist_seq for person in [a, b, c]] == [1, 2, 3]
    initial_path = notice(business, a, NotificationKind.WAITLIST).payload["manage_path"]
    business.cancel(owner)
    for promoted, next_person in [(a, b), (b, c)]:
        assert business.private(promoted).status == "confirmed"
        assert business.private(promoted).waitlist_seq is None
        assert notice(business, promoted, NotificationKind.TICKET).payload["ticket_code"]
        assert business.private(next_person).status == "waitlisted"
        business.cancel(promoted)
    assert business.private(c).status == "confirmed"
    first_notice = notice(business, a, NotificationKind.WAITLIST)
    assert first_notice.payload["manage_path"] == initial_path
    assert business.event(event.id).confirmed == 1


def test_newcomer_does_not_bypass_queue_during_cancel(business: Business) -> None:
    event = business.create()
    owner = business.join(event.id, "owner@example.test")
    a = business.join(event.id, "a@example.test")
    b = business.join(event.id, "b@example.test")
    results = parallel_while_event_locked(
        business,
        event.id,
        lambda: business.cancel(owner),
        lambda: business.join(event.id, "new@example.test"),
    )
    assert not any(isinstance(result, DomainError) for result in results)
    assert business.private(a).status == "confirmed"
    assert business.private(b).status == "waitlisted"
    newcomer = business.join(event.id, "new@example.test")
    assert business.private(newcomer).waitlist_seq > business.private(b).waitlist_seq


def test_waitlisted_cancel_and_repeated_cancel_do_not_free_extra_place(business: Business) -> None:
    event = business.create()
    owner, a, b = [business.join(event.id, f"{name}@example.test") for name in "oab"]
    business.cancel(b)
    assert business.private(owner).status == "confirmed"
    assert business.private(a).status == "waitlisted"
    business.cancel(owner)
    ticket = business.private(a).ticket_code
    business.cancel(owner)
    assert business.private(a).ticket_code == ticket
    assert len([m for m in business.messages(a) if m.kind == NotificationKind.TICKET]) == 1
    assert business.event(event.id).confirmed == 1


@pytest.mark.parametrize("state", ["confirmed", "waitlisted", "cancelled"])
def test_public_repeat_is_noop_for_every_state_even_after_start(
    business: Business, state: str
) -> None:
    event = business.create()
    if state == "waitlisted":
        business.join(event.id, "owner@example.test")
    person = business.join(event.id, "user@example.test")
    if state == "cancelled":
        business.cancel(person)
    before = business.private(person)
    messages = [(m.id, m.payload, m.status, m.available_at) for m in business.messages(person)]
    business.clock.now = event.starts_at
    assert business.join(event.id, " USER@example.test ") == person
    assert business.private(person) == before
    assert [
        (m.id, m.payload, m.status, m.available_at) for m in business.messages(person)
    ] == messages


def test_resume_keeps_identity_and_token_and_issues_new_ticket(business: Business) -> None:
    event = business.create()
    person = business.join(event.id, "user@example.test")
    before = business.private(person)
    reminder_id = notice(business, person, NotificationKind.REMINDER).id
    business.cancel(person)
    assert business.private(person).ticket_code is None
    assert all(message.status == "cancelled" for message in business.messages(person))
    resumed = business.resume(person)
    assert resumed.id == before.id
    assert resumed.participation_no == 2
    assert resumed.ticket_code and resumed.ticket_code != before.ticket_code
    assert business.private(person) == resumed
    reminder = notice(business, person, NotificationKind.REMINDER)
    assert reminder.id == reminder_id
    assert reminder.status == "pending"
    assert reminder.payload["participation_no"] == 2
    assert len([m for m in business.messages(person) if m.kind == NotificationKind.REMINDER]) == 1
    with pytest.raises(Conflict, match="Участие изменилось"):
        business.cancel(person, 1)
    business.cancel(person, 2)
    with pytest.raises(Conflict):
        business.resume(person, 1)


def test_resume_enters_queue_tail_and_repeats_once_concurrently(business: Business) -> None:
    event = business.create()
    person = business.join(event.id, "user@example.test")
    business.cancel(person)
    business.join(event.id, "owner@example.test")
    waiting = business.join(event.id, "waiting@example.test")
    results = parallel_while_event_locked(
        business, event.id, lambda: business.resume(person), lambda: business.resume(person)
    )
    assert results[0] == results[1]
    assert results[0].participation_no == 2
    assert results[0].waitlist_seq == business.private(waiting).waitlist_seq + 1
    assert results[0].ticket_code is None
    assert len(business.messages(person)) == 3  # old ticket, one reminder, new waitlist


def test_two_concurrent_checkins_preserve_first_timestamp_and_counter(business: Business) -> None:
    event = business.create()
    person = business.join(event.id, "user@example.test")
    ticket = business.private(person).ticket_code
    business.clock.now = event.starts_at
    results = parallel_while_event_locked(
        business,
        event.id,
        lambda: business.checkin(event.id, ticket),
        lambda: business.checkin(event.id, ticket),
    )
    assert sum(isinstance(result, Conflict) for result in results) == 1
    assert business.event(event.id).checked_in == 1
    assert business.event(event.id).confirmed == 1
    business.clock.now += timedelta(seconds=1)
    with pytest.raises(Conflict) as error:
        business.checkin(event.id, ticket)
    assert error.value.code == "already_checked_in"
    assert business.private(person).checked_in_at == event.starts_at
    with pytest.raises(Conflict) as error:
        business.cancel(person)
    assert error.value.code == "already_checked_in"


def test_foreign_cancelled_and_unknown_tickets_are_rejected(business: Business) -> None:
    event, other = business.create(), business.create()
    person = business.join(event.id, "user@example.test")
    foreign = business.join(other.id, "other@example.test")
    cancelled_ticket = business.private(person).ticket_code
    foreign_ticket = business.private(foreign).ticket_code
    business.cancel(person)
    business.clock.now = event.starts_at
    for ticket in [cancelled_ticket, foreign_ticket, "unknown-ticket"]:
        with pytest.raises(NotFound):
            business.checkin(event.id, ticket)
    assert business.event(event.id).checked_in == 0


def test_schedule_versions_repeats_aba_and_outbox_snapshots(business: Business) -> None:
    event = business.create()
    confirmed = business.join(event.id, "user@example.test")
    waiting = business.join(event.id, "wait@example.test")
    cancelled = business.join(event.id, "cancel@example.test")
    business.cancel(cancelled)
    new_date = event.starts_at + timedelta(days=1)
    moved = business.schedule(event.id, new_date, 1)
    assert moved.schedule_version == 2
    assert business.schedule(event.id, new_date, 1) == moved
    with pytest.raises(Conflict):
        business.schedule(event.id, new_date + timedelta(days=1), 1)
    returned = business.schedule(event.id, event.starts_at, 2)
    assert returned.schedule_version == 3
    for person in [confirmed, waiting]:
        messages = business.messages(person)
        notices = [message for message in messages if message.kind == NotificationKind.RESCHEDULED]
        assert len(notices) == 2
        first = next(m for m in notices if m.payload["schedule_version"] == 2)
        assert first.payload["old_starts_at"] == event.starts_at.isoformat()
        assert first.payload["new_starts_at"] == new_date.isoformat()
        assert notice(business, person, NotificationKind.REMINDER).available_at == (
            event.starts_at - timedelta(hours=24)
        )
    assert all(m.kind != NotificationKind.RESCHEDULED for m in business.messages(cancelled))


@pytest.mark.parametrize("status", [OutboxStatus.PENDING, OutboxStatus.SENT])
def test_prepared_messages_never_change_on_reschedule_cancel_resume(
    business: Business, status: OutboxStatus
) -> None:
    event = business.create()
    person = business.join(event.id, "user@example.test")
    original = business.messages(person)
    with Session(business.engine) as session, session.begin():
        for message in session.scalars(
            select(EmailOutbox).where(EmailOutbox.registration_id == person.id)
        ):
            message.prepared_at = business.clock()
            message.status = status
            message.payload = {**message.payload, "mime": "immutable MIME"}
    frozen = {
        m.id: (deepcopy(m.payload), m.prepared_at, m.available_at, m.status)
        for m in business.messages(person)
    }
    business.schedule(event.id, event.starts_at + timedelta(days=1), 1)
    business.cancel(person)
    business.resume(person)
    for message in business.messages(person):
        if message.id in frozen:
            assert (
                message.payload,
                message.prepared_at,
                message.available_at,
                message.status,
            ) == frozen[message.id]
    assert len([m for m in business.messages(person) if m.kind == NotificationKind.REMINDER]) == 1
    assert len(original) == 2


def test_late_registration_and_reminder_reschedule_use_due_now(business: Business) -> None:
    event = business.create(starts_at=business.clock() + timedelta(hours=1))
    person = business.join(event.id, "user@example.test")
    reminder = notice(business, person, NotificationKind.REMINDER)
    assert reminder.available_at == business.clock()
    business.schedule(event.id, event.starts_at + timedelta(days=3), 1)
    reminder = notice(business, person, NotificationKind.REMINDER)
    assert reminder.available_at == event.starts_at + timedelta(days=2)


def test_rollback_removes_registration_and_all_outbox_entries(business: Business) -> None:
    event = business.create()
    with (
        patch("app.services.registrations.sync_reminder", side_effect=RuntimeError("failure")),
        pytest.raises(RuntimeError, match="failure"),
    ):
        business.join(event.id, "user@example.test")
    assert business.event(event.id).confirmed == 0
    with Session(business.engine) as session:
        ids = select(Registration.id).where(Registration.event_id == event.id)
        assert session.scalars(ids).all() == []
        assert (
            session.scalars(select(EmailOutbox).where(EmailOutbox.registration_id.in_(ids))).all()
            == []
        )


def test_cancel_promotion_and_outbox_roll_back_together(business: Business) -> None:
    event = business.create()
    owner = business.join(event.id, "owner@example.test")
    waiting = business.join(event.id, "wait@example.test")
    old_ticket = business.private(owner).ticket_code
    old_messages = [(m.id, m.payload, m.status) for m in business.messages(waiting)]
    with (
        patch(
            "app.services.registrations.queue_participation_notice",
            side_effect=RuntimeError("failure"),
        ),
        pytest.raises(RuntimeError),
    ):
        business.cancel(owner)
    assert business.private(owner).ticket_code == old_ticket
    assert business.private(waiting).status == "waitlisted"
    assert [(m.id, m.payload, m.status) for m in business.messages(waiting)] == old_messages


def test_concurrent_duplicate_cancel_promotes_only_one(business: Business) -> None:
    event = business.create()
    owner, first, second = [business.join(event.id, f"{name}@example.test") for name in "oab"]
    results = parallel_while_event_locked(
        business, event.id, lambda: business.cancel(owner), lambda: business.cancel(owner)
    )
    assert results[0] == results[1]
    assert business.private(first).status == "confirmed"
    assert business.private(second).status == "waitlisted"
    assert business.event(event.id).confirmed == 1


def test_current_time_is_read_after_waiting_for_event_lock(business: Business) -> None:
    event = business.create()

    def reach_start() -> None:
        business.clock.now = event.starts_at

    def late_registration() -> None:
        with Session(business.engine) as session:
            registrations.register(session, event.id, "late@example.test", business.clock)

    results = parallel_while_event_locked(
        business,
        event.id,
        late_registration,
        lambda: business.schedule(event.id, event.starts_at + timedelta(days=1), 1),
        before_release=reach_start,
    )
    assert results[0] is None
    assert isinstance(results[1], Conflict) and results[1].code == "event_started"
    assert business.event(event.id).confirmed == 0
    assert business.event(event.id).schedule_version == 1


def test_resume_time_rules_and_noop_retries_after_start(business: Business) -> None:
    event = business.create()
    first = business.join(event.id, "one@example.test")
    second = business.join(event.id, "two@example.test")
    business.cancel(first)
    business.resume(first)
    business.cancel(second)
    business.clock.now = event.starts_at
    # Replays of completed transitions do not become new transitions after start.
    assert business.resume(first).participation_no == 2
    assert business.cancel(second).status == "cancelled"
    with pytest.raises(Conflict) as error:
        business.resume(second)
    assert error.value.code == "event_started"


def test_schedule_rolls_back_date_version_and_outbox(business: Business) -> None:
    event = business.create()
    person = business.join(event.id, "user@example.test")
    before = business.event(event.id)
    original = [(m.id, m.payload, m.available_at) for m in business.messages(person)]
    actual_enqueue = events.queue_reschedule

    def fail_after_enqueue(
        session: Session, entry: Registration, item: Event, old_time: datetime, now: datetime
    ) -> None:
        actual_enqueue(session, entry, item, old_time, now)
        session.flush()
        raise RuntimeError("failure")

    with (
        patch("app.services.events.queue_reschedule", side_effect=fail_after_enqueue),
        pytest.raises(RuntimeError),
    ):
        business.schedule(event.id, event.starts_at + timedelta(days=1), 1)
    assert business.event(event.id) == before
    assert [(m.id, m.payload, m.available_at) for m in business.messages(person)] == original


def test_failed_unprepared_notice_is_updated_without_automatic_retry(business: Business) -> None:
    event = business.create()
    person = business.join(event.id, "user@example.test")
    ticket = notice(business, person, NotificationKind.TICKET)
    with Session(business.engine) as session, session.begin():
        message = session.get(EmailOutbox, ticket.id)
        message.status = OutboxStatus.FAILED
        message.last_error = "preparation failure"
        message.attempts = 3
    moved = business.schedule(event.id, event.starts_at + timedelta(days=1), 1)
    message = notice(business, person, NotificationKind.TICKET)
    assert message.payload["starts_at"] == moved.starts_at.isoformat()
    assert message.status == "failed" and message.attempts == 3
    assert message.last_error == "preparation failure"


def test_timezone_is_mandatory_in_service(business: Business) -> None:
    with (
        Session(business.engine) as session,
        pytest.raises(ValueError, match="Timezone-aware"),
    ):
        events.create_event(
            session, "Описание", business.clock().replace(tzinfo=None), 1, business.clock
        )


def test_time_rules_and_timezone_boundaries(business: Business) -> None:
    almaty = timezone(timedelta(hours=5))
    starts = (business.clock() + timedelta(seconds=1)).astimezone(almaty)
    event = business.create(starts_at=starts)
    assert event.starts_at.tzinfo == UTC
    person = business.join(event.id, "user@example.test")
    with pytest.raises(Conflict):
        business.checkin(event.id, business.private(person).ticket_code)
    business.clock.now = event.starts_at
    for operation in [
        lambda: business.cancel(person),
        lambda: business.schedule(event.id, event.starts_at + timedelta(days=1), 1),
        lambda: business.create(starts_at=business.clock()),
    ]:
        with pytest.raises(Conflict):
            operation()
    with Session(business.engine) as session:
        registrations.register(session, event.id, "new@example.test", business.clock)
        assert (
            session.scalar(select(Registration.id).where(Registration.email == "new@example.test"))
            is None
        )
    assert (
        business.checkin(event.id, business.private(person).ticket_code).checked_in_at
        == business.clock()
    )


@pytest.mark.parametrize(
    "email", ["bad", "a..b@example.test", "a@-example.test", "a b@example.test"]
)
def test_invalid_email_is_rejected_by_service(business: Business, email: str) -> None:
    with pytest.raises(InvalidInput):
        business.join(business.create().id, email)
