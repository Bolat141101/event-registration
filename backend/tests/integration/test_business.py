import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def notice(business: Business, person: Participant, kind: NotificationKind) -> EmailOutbox:
    return next(message for message in await business.messages(person) if message.kind == kind)


async def test_two_people_concurrently_take_last_place(business: Business) -> None:
    event = await business.create()
    people = await parallel_while_event_locked(
        business,
        event.id,
        lambda: business.join(event.id, "one@example.test"),
        lambda: business.join(event.id, "two@example.test"),
    )
    assert all(isinstance(person, Participant) for person in people)
    states = [(await business.private(person)) for person in people]
    assert {state.status for state in states} == {"confirmed", "waitlisted"}
    assert sum(state.ticket_code is not None for state in states) == 1
    assert sorted(state.waitlist_seq for state in states if state.waitlist_seq) == [1]
    assert (await business.event(event.id)).confirmed == 1
    assert (await business.event(event.id)).waitlisted == 1
    assert all([len(await business.messages(person)) == 2 for person in people])


async def test_same_normalized_email_concurrently_is_one_registration(business: Business) -> None:
    event = await business.create()
    people = await parallel_while_event_locked(
        business,
        event.id,
        lambda: business.join(event.id, " User@EXAMPLE.test "),
        lambda: business.join(event.id, "user@example.test"),
    )
    assert people[0] == people[1]
    assert len(await business.messages(people[0])) == 2
    assert (await business.event(event.id)).confirmed == 1
    assert (await business.event(event.id)).waitlisted == 0


async def test_email_in_different_events_and_plus_dot_are_preserved(business: Business) -> None:
    first, second = (await business.create(3)), (await business.create())
    people = [
        (await business.join(first.id, value))
        for value in ("Some.One+tag@example.test", "some.one@example.test", "someone@example.test")
    ]
    other = await business.join(second.id, "Some.One+tag@example.test")
    assert len({person.id for person in [*people, other]}) == 4
    async with AsyncSession(business.engine, expire_on_commit=False) as session:
        assert (await session.get(Registration, people[0].id)).email == "some.one+tag@example.test"


async def test_fifo_abc_promotion_works_without_worker(business: Business) -> None:
    event = await business.create()
    owner, a, b, c = [(await business.join(event.id, f"{name}@example.test")) for name in "oabc"]
    assert [(await business.private(person)).waitlist_seq for person in [a, b, c]] == [1, 2, 3]
    initial_path = (await notice(business, a, NotificationKind.WAITLIST)).payload["manage_path"]
    await business.cancel(owner)
    for promoted, next_person in [(a, b), (b, c)]:
        assert (await business.private(promoted)).status == "confirmed"
        assert (await business.private(promoted)).waitlist_seq is None
        assert (await notice(business, promoted, NotificationKind.TICKET)).payload["ticket_code"]
        assert (await business.private(next_person)).status == "waitlisted"
        await business.cancel(promoted)
    assert (await business.private(c)).status == "confirmed"
    first_notice = await notice(business, a, NotificationKind.WAITLIST)
    assert first_notice.payload["manage_path"] == initial_path
    assert (await business.event(event.id)).confirmed == 1


async def test_newcomer_does_not_bypass_queue_during_cancel(business: Business) -> None:
    event = await business.create()
    owner = await business.join(event.id, "owner@example.test")
    a = await business.join(event.id, "a@example.test")
    b = await business.join(event.id, "b@example.test")
    results = await parallel_while_event_locked(
        business,
        event.id,
        lambda: business.cancel(owner),
        lambda: business.join(event.id, "new@example.test"),
    )
    assert not any(isinstance(result, DomainError) for result in results)
    assert (await business.private(a)).status == "confirmed"
    assert (await business.private(b)).status == "waitlisted"
    newcomer = await business.join(event.id, "new@example.test")
    assert (await business.private(newcomer)).waitlist_seq > (
        await business.private(b)
    ).waitlist_seq


async def test_waitlisted_cancel_and_repeated_cancel_do_not_free_extra_place(
    business: Business,
) -> None:
    event = await business.create()
    owner, a, b = [(await business.join(event.id, f"{name}@example.test")) for name in "oab"]
    await business.cancel(b)
    assert (await business.private(owner)).status == "confirmed"
    assert (await business.private(a)).status == "waitlisted"
    await business.cancel(owner)
    ticket = (await business.private(a)).ticket_code
    await business.cancel(owner)
    assert (await business.private(a)).ticket_code == ticket
    assert len([m for m in (await business.messages(a)) if m.kind == NotificationKind.TICKET]) == 1
    assert (await business.event(event.id)).confirmed == 1


@pytest.mark.parametrize("state", ["confirmed", "waitlisted", "cancelled"])
async def test_public_repeat_is_noop_for_every_state_even_after_start(
    business: Business, state: str
) -> None:
    event = await business.create()
    if state == "waitlisted":
        await business.join(event.id, "owner@example.test")
    person = await business.join(event.id, "user@example.test")
    if state == "cancelled":
        await business.cancel(person)
    before = await business.private(person)
    messages = [
        (m.id, m.payload, m.status, m.available_at) for m in (await business.messages(person))
    ]
    business.clock.now = event.starts_at
    assert (await business.join(event.id, " USER@example.test ")) == person
    assert (await business.private(person)) == before
    assert [
        (m.id, m.payload, m.status, m.available_at) for m in (await business.messages(person))
    ] == messages


async def test_resume_keeps_identity_and_token_and_issues_new_ticket(business: Business) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    before = await business.private(person)
    reminder_id = (await notice(business, person, NotificationKind.REMINDER)).id
    await business.cancel(person)
    assert (await business.private(person)).ticket_code is None
    assert all(message.status == "cancelled" for message in await business.messages(person))
    resumed = await business.resume(person)
    assert resumed.id == before.id
    assert resumed.participation_no == 2
    assert resumed.ticket_code and resumed.ticket_code != before.ticket_code
    assert (await business.private(person)) == resumed
    reminder = await notice(business, person, NotificationKind.REMINDER)
    assert reminder.id == reminder_id
    assert reminder.status == "pending"
    assert reminder.payload["participation_no"] == 2
    assert (
        len([m for m in (await business.messages(person)) if m.kind == NotificationKind.REMINDER])
        == 1
    )
    with pytest.raises(Conflict, match="Участие изменилось"):
        await business.cancel(person, 1)
    await business.cancel(person, 2)
    with pytest.raises(Conflict):
        await business.resume(person, 1)


async def test_resume_enters_queue_tail_and_repeats_once_concurrently(business: Business) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    await business.cancel(person)
    await business.join(event.id, "owner@example.test")
    waiting = await business.join(event.id, "waiting@example.test")
    results = await parallel_while_event_locked(
        business, event.id, lambda: business.resume(person), lambda: business.resume(person)
    )
    assert results[0] == results[1]
    assert results[0].participation_no == 2
    assert results[0].waitlist_seq == (await business.private(waiting)).waitlist_seq + 1
    assert results[0].ticket_code is None
    assert len(await business.messages(person)) == 3  # old ticket, one reminder, new waitlist


async def test_two_concurrent_checkins_preserve_first_timestamp_and_counter(
    business: Business,
) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    ticket = (await business.private(person)).ticket_code
    business.clock.now = event.starts_at
    results = await parallel_while_event_locked(
        business,
        event.id,
        lambda: business.checkin(event.id, ticket),
        lambda: business.checkin(event.id, ticket),
    )
    assert sum(isinstance(result, Conflict) for result in results) == 1
    assert (await business.event(event.id)).checked_in == 1
    assert (await business.event(event.id)).confirmed == 1
    business.clock.now += timedelta(seconds=1)
    with pytest.raises(Conflict) as error:
        await business.checkin(event.id, ticket)
    assert error.value.code == "already_checked_in"
    assert (await business.private(person)).checked_in_at == event.starts_at
    with pytest.raises(Conflict) as error:
        await business.cancel(person)
    assert error.value.code == "already_checked_in"


async def test_foreign_cancelled_and_unknown_tickets_are_rejected(business: Business) -> None:
    event, other = (await business.create()), (await business.create())
    person = await business.join(event.id, "user@example.test")
    foreign = await business.join(other.id, "other@example.test")
    cancelled_ticket = (await business.private(person)).ticket_code
    foreign_ticket = (await business.private(foreign)).ticket_code
    await business.cancel(person)
    business.clock.now = event.starts_at
    for ticket in [cancelled_ticket, foreign_ticket, "unknown-ticket"]:
        with pytest.raises(NotFound):
            await business.checkin(event.id, ticket)
    assert (await business.event(event.id)).checked_in == 0


async def test_schedule_versions_repeats_aba_and_outbox_snapshots(business: Business) -> None:
    event = await business.create()
    confirmed = await business.join(event.id, "user@example.test")
    waiting = await business.join(event.id, "wait@example.test")
    cancelled = await business.join(event.id, "cancel@example.test")
    await business.cancel(cancelled)
    new_date = event.starts_at + timedelta(days=1)
    moved = await business.schedule(event.id, new_date, 1)
    assert moved.schedule_version == 2
    assert (await business.schedule(event.id, new_date, 1)) == moved
    with pytest.raises(Conflict):
        await business.schedule(event.id, new_date + timedelta(days=1), 1)
    returned = await business.schedule(event.id, event.starts_at, 2)
    assert returned.schedule_version == 3
    for person in [confirmed, waiting]:
        messages = await business.messages(person)
        notices = [message for message in messages if message.kind == NotificationKind.RESCHEDULED]
        assert len(notices) == 2
        first = next(m for m in notices if m.payload["schedule_version"] == 2)
        assert first.payload["old_starts_at"] == event.starts_at.isoformat()
        assert first.payload["new_starts_at"] == new_date.isoformat()
        assert (await notice(business, person, NotificationKind.REMINDER)).available_at == (
            event.starts_at - timedelta(hours=24)
        )
    assert all(m.kind != NotificationKind.RESCHEDULED for m in await business.messages(cancelled))


@pytest.mark.parametrize("status", [OutboxStatus.PENDING, OutboxStatus.SENT])
async def test_prepared_messages_never_change_on_reschedule_cancel_resume(
    business: Business, status: OutboxStatus
) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    original = await business.messages(person)
    async with AsyncSession(business.engine, expire_on_commit=False) as session, session.begin():
        for message in await session.scalars(
            select(EmailOutbox).where(EmailOutbox.registration_id == person.id)
        ):
            message.prepared_at = business.clock()
            message.status = status
            message.payload = {**message.payload, "mime": "immutable MIME"}
    frozen = {
        m.id: (deepcopy(m.payload), m.prepared_at, m.available_at, m.status)
        for m in (await business.messages(person))
    }
    await business.schedule(event.id, event.starts_at + timedelta(days=1), 1)
    await business.cancel(person)
    await business.resume(person)
    for message in await business.messages(person):
        if message.id in frozen:
            assert (
                message.payload,
                message.prepared_at,
                message.available_at,
                message.status,
            ) == frozen[message.id]
    assert (
        len([m for m in (await business.messages(person)) if m.kind == NotificationKind.REMINDER])
        == 1
    )
    assert len(original) == 2


async def test_late_registration_and_reminder_reschedule_use_due_now(business: Business) -> None:
    event = await business.create(starts_at=business.clock() + timedelta(hours=1))
    person = await business.join(event.id, "user@example.test")
    reminder = await notice(business, person, NotificationKind.REMINDER)
    assert reminder.available_at == business.clock()
    await business.schedule(event.id, event.starts_at + timedelta(days=3), 1)
    reminder = await notice(business, person, NotificationKind.REMINDER)
    assert reminder.available_at == event.starts_at + timedelta(days=2)


async def test_rollback_removes_registration_and_all_outbox_entries(business: Business) -> None:
    event = await business.create()
    with (
        patch("app.services.registrations.sync_reminder", side_effect=RuntimeError("failure")),
        pytest.raises(RuntimeError, match="failure"),
    ):
        await business.join(event.id, "user@example.test")
    assert (await business.event(event.id)).confirmed == 0
    async with AsyncSession(business.engine, expire_on_commit=False) as session:
        ids = select(Registration.id).where(Registration.event_id == event.id)
        assert (await session.scalars(ids)).all() == []
        assert (
            await session.scalars(select(EmailOutbox).where(EmailOutbox.registration_id.in_(ids)))
        ).all() == []


async def test_cancel_promotion_and_outbox_roll_back_together(business: Business) -> None:
    event = await business.create()
    owner = await business.join(event.id, "owner@example.test")
    waiting = await business.join(event.id, "wait@example.test")
    old_ticket = (await business.private(owner)).ticket_code
    old_messages = [(m.id, m.payload, m.status) for m in (await business.messages(waiting))]
    with (
        patch(
            "app.services.registrations.queue_participation_notice",
            side_effect=RuntimeError("failure"),
        ),
        pytest.raises(RuntimeError),
    ):
        await business.cancel(owner)
    assert (await business.private(owner)).ticket_code == old_ticket
    assert (await business.private(waiting)).status == "waitlisted"
    assert [(m.id, m.payload, m.status) for m in (await business.messages(waiting))] == old_messages


async def test_concurrent_duplicate_cancel_promotes_only_one(business: Business) -> None:
    event = await business.create()
    owner, first, second = [
        (await business.join(event.id, f"{name}@example.test")) for name in "oab"
    ]
    results = await parallel_while_event_locked(
        business, event.id, lambda: business.cancel(owner), lambda: business.cancel(owner)
    )
    assert results[0] == results[1]
    assert (await business.private(first)).status == "confirmed"
    assert (await business.private(second)).status == "waitlisted"
    assert (await business.event(event.id)).confirmed == 1


async def test_current_time_is_read_after_waiting_for_event_lock(business: Business) -> None:
    event = await business.create()

    def reach_start() -> None:
        business.clock.now = event.starts_at

    async def late_registration() -> None:
        async with AsyncSession(business.engine, expire_on_commit=False) as session:
            await registrations.register(session, event.id, "late@example.test", business.clock)

    results = await parallel_while_event_locked(
        business,
        event.id,
        late_registration,
        lambda: business.schedule(event.id, event.starts_at + timedelta(days=1), 1),
        before_release=reach_start,
    )
    assert results[0] is None
    assert isinstance(results[1], Conflict) and results[1].code == "event_started"
    assert (await business.event(event.id)).confirmed == 0
    assert (await business.event(event.id)).schedule_version == 1


async def test_resume_time_rules_and_noop_retries_after_start(business: Business) -> None:
    event = await business.create()
    first = await business.join(event.id, "one@example.test")
    second = await business.join(event.id, "two@example.test")
    await business.cancel(first)
    await business.resume(first)
    await business.cancel(second)
    business.clock.now = event.starts_at
    # Replays of completed transitions do not become new transitions after start.
    assert (await business.resume(first)).participation_no == 2
    assert (await business.cancel(second)).status == "cancelled"
    with pytest.raises(Conflict) as error:
        await business.resume(second)
    assert error.value.code == "event_started"


async def test_schedule_rolls_back_date_version_and_outbox(business: Business) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    before = await business.event(event.id)
    original = [(m.id, m.payload, m.available_at) for m in (await business.messages(person))]
    actual_enqueue = events.queue_reschedule

    async def fail_after_enqueue(
        session: AsyncSession, entry: Registration, item: Event, old_time: datetime, now: datetime
    ) -> None:
        await actual_enqueue(session, entry, item, old_time, now)
        await session.flush()
        raise RuntimeError("failure")

    with (
        patch("app.services.events.queue_reschedule", side_effect=fail_after_enqueue),
        pytest.raises(RuntimeError),
    ):
        await business.schedule(event.id, event.starts_at + timedelta(days=1), 1)
    assert (await business.event(event.id)) == before
    assert [
        (m.id, m.payload, m.available_at) for m in (await business.messages(person))
    ] == original


async def test_failed_unprepared_notice_is_updated_without_automatic_retry(
    business: Business,
) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@example.test")
    ticket = await notice(business, person, NotificationKind.TICKET)
    async with AsyncSession(business.engine, expire_on_commit=False) as session, session.begin():
        message = await session.get(EmailOutbox, ticket.id)
        message.status = OutboxStatus.FAILED
        message.last_error = "preparation failure"
        message.attempts = 3
    moved = await business.schedule(event.id, event.starts_at + timedelta(days=1), 1)
    message = await notice(business, person, NotificationKind.TICKET)
    assert message.payload["starts_at"] == moved.starts_at.isoformat()
    assert message.status == "failed" and message.attempts == 3
    assert message.last_error == "preparation failure"


async def test_timezone_is_mandatory_in_service(business: Business) -> None:
    async with AsyncSession(business.engine, expire_on_commit=False) as session:
        with pytest.raises(ValueError, match="Timezone-aware"):
            (
                await events.create_event(
                    session, "Описание", business.clock().replace(tzinfo=None), 1, business.clock
                )
            )


async def test_time_rules_and_timezone_boundaries(business: Business) -> None:
    almaty = timezone(timedelta(hours=5))
    starts = (business.clock() + timedelta(seconds=1)).astimezone(almaty)
    event = await business.create(starts_at=starts)
    assert event.starts_at.tzinfo == UTC
    person = await business.join(event.id, "user@example.test")
    with pytest.raises(Conflict):
        await business.checkin(event.id, (await business.private(person)).ticket_code)
    business.clock.now = event.starts_at
    for operation in [
        lambda: business.cancel(person),
        lambda: business.schedule(event.id, event.starts_at + timedelta(days=1), 1),
        lambda: business.create(starts_at=business.clock()),
    ]:
        with pytest.raises(Conflict):
            await operation()
    async with AsyncSession(business.engine, expire_on_commit=False) as session:
        await registrations.register(session, event.id, "new@example.test", business.clock)
        assert (
            await session.scalar(
                select(Registration.id).where(Registration.email == "new@example.test")
            )
        ) is None
    assert (
        await business.checkin(event.id, (await business.private(person)).ticket_code)
    ).checked_in_at == business.clock()


@pytest.mark.parametrize(
    "email", ["bad", "a..b@example.test", "a@-example.test", "a b@example.test"]
)
async def test_invalid_email_is_rejected_by_service(business: Business, email: str) -> None:
    with pytest.raises(InvalidInput):
        await business.join((await business.create()).id, email)


async def test_cancellation_rolls_back_registration_outbox_and_releases_lock(
    business: Business,
) -> None:
    event = await business.create()
    written = asyncio.Event()

    async def pause_before_commit(session: AsyncSession, *_args: object) -> None:
        await session.flush()
        written.set()
        await asyncio.Event().wait()

    with patch("app.services.registrations.sync_reminder", side_effect=pause_before_commit):
        async with asyncio.TaskGroup() as group:
            task = group.create_task(business.join(event.id, "cancelled@example.test"))
            await asyncio.wait_for(written.wait(), timeout=5)
            task.cancel()
    assert task.cancelled()
    assert (await business.event(event.id)).confirmed == 0
    async with AsyncSession(business.engine) as session:
        ids = select(Registration.id).where(Registration.event_id == event.id)
        assert (await session.scalars(ids)).all() == []
        assert (
            await session.scalars(select(EmailOutbox).where(EmailOutbox.registration_id.in_(ids)))
        ).all() == []
    # A fresh transaction can acquire the same event and claim its only place.
    async with asyncio.timeout(5):
        person = await business.join(event.id, "replacement@example.test")
    assert (await business.private(person)).status == "confirmed"
