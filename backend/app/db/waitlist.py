"""Database operation used by future registration services, inside their transaction."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Event, Registration, RegistrationStatus


def next_waitlist_seq(session: Session, event_id: UUID) -> int:
    """Lock the event, then read MAX in a separate READ COMMITTED statement.

    Call before mutating registrations. The caller must insert/update the waitlist
    entry in this same transaction; this function never commits or reserves a number.
    Every future registration, cancellation and promotion must use the event lock.
    """
    if not session.in_transaction():
        raise RuntimeError("next_waitlist_seq requires an explicit caller transaction")
    with session.no_autoflush:
        event = session.scalar(select(Event.id).where(Event.id == event_id).with_for_update())
    if event is None:
        raise LookupError(f"Event {event_id} does not exist")
    maximum = session.scalar(
        select(func.coalesce(func.max(Registration.waitlist_seq), 0)).where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.WAITLISTED,
        )
    )
    assert maximum is not None
    return maximum + 1
