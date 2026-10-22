"""Enqueue/update messages in the caller's event-locked transaction; never commit."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EmailOutbox,
    Event,
    NotificationKind,
    OutboxStatus,
    Registration,
)


def context(entry: Registration, event: Event) -> dict[str, Any]:
    return {
        "recipient": entry.email,
        "event_id": str(event.id),
        "description": event.description,
        "starts_at": event.starts_at.isoformat(),
        "schedule_version": event.schedule_version,
        "participation_no": entry.participation_no,
        "registration_status": entry.status.value,
        "ticket_code": entry.ticket_code,
    }


def enqueue(
    session: Session,
    entry: Registration,
    kind: NotificationKind,
    key: str,
    payload: dict[str, Any],
    available_at: datetime,
) -> EmailOutbox:
    message = session.scalar(select(EmailOutbox).where(EmailOutbox.dedup_key == key))
    if message is None:
        message = EmailOutbox(
            registration_id=entry.id,
            kind=kind,
            dedup_key=key,
            payload=payload,
            available_at=available_at,
        )
        session.add(message)
    # The event lock serializes logical message creation. Do not overwrite a retry
    # or an already prepared message when the same logical operation is repeated.
    return message


def queue_participation_notice(
    session: Session,
    entry: Registration,
    event: Event,
    now: datetime,
    initial_token: str | None = None,
) -> None:
    kind = NotificationKind.TICKET if entry.ticket_code else NotificationKind.WAITLIST
    payload = context(entry, event)
    if initial_token is not None:
        payload["manage_path"] = f"/registration#token={initial_token}"
    enqueue(session, entry, kind, f"{kind.value}:{entry.id}:{entry.participation_no}", payload, now)


def sync_reminder(session: Session, entry: Registration, event: Event, now: datetime) -> None:
    deadline = max(now, event.starts_at - timedelta(hours=24))
    payload = context(entry, event)
    message = enqueue(
        session, entry, NotificationKind.REMINDER, f"reminder:{entry.id}", payload, deadline
    )
    if message.prepared_at is None:
        message.payload = payload
        message.available_at = deadline
        if message.status == OutboxStatus.CANCELLED:
            message.status = OutboxStatus.PENDING


def refresh_unprepared_notices(session: Session, entry: Registration, event: Event) -> None:
    messages = session.scalars(
        select(EmailOutbox).where(
            EmailOutbox.registration_id == entry.id,
            EmailOutbox.prepared_at.is_(None),
            EmailOutbox.kind.in_([NotificationKind.TICKET, NotificationKind.WAITLIST]),
            EmailOutbox.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
        )
    )
    for message in messages:
        if message.payload.get("participation_no") != entry.participation_no:
            message.status = OutboxStatus.CANCELLED
            continue
        payload = context(entry, event)
        if message.kind == NotificationKind.WAITLIST:
            # Keep the initial management link after promotion, without a second
            # ticket notification disguised as a waitlist email.
            payload["ticket_code"] = None
        if "manage_path" in message.payload:
            payload["manage_path"] = message.payload["manage_path"]
        message.payload = payload


def cancel_unprepared(session: Session, entry: Registration) -> None:
    for message in session.scalars(
        select(EmailOutbox).where(
            EmailOutbox.registration_id == entry.id, EmailOutbox.prepared_at.is_(None)
        )
    ):
        message.status = OutboxStatus.CANCELLED


def queue_reschedule(
    session: Session, entry: Registration, event: Event, old_starts_at: datetime, now: datetime
) -> None:
    refresh_unprepared_notices(session, entry, event)
    sync_reminder(session, entry, event, now)
    payload = context(entry, event)
    payload.update(
        old_starts_at=old_starts_at.isoformat(), new_starts_at=event.starts_at.isoformat()
    )
    enqueue(
        session,
        entry,
        NotificationKind.RESCHEDULED,
        f"rescheduled:{entry.id}:{event.schedule_version}",
        payload,
        now,
    )
