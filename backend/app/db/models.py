from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, validates


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class RegistrationStatus(StrEnum):
    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"


class NotificationKind(StrEnum):
    TICKET = "ticket"
    WAITLIST = "waitlist"
    REMINDER = "reminder"
    RESCHEDULED = "rescheduled"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    FORWARDED = "forwarded"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="positive_capacity"),
        CheckConstraint("schedule_version > 0", name="positive_schedule_version"),
        CheckConstraint("length(btrim(description)) > 0", name="nonempty_description"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    description: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    schedule_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "email", name="uq_registrations_event_email"),
        UniqueConstraint("event_id", "waitlist_seq", name="uq_registrations_event_waitlist_seq"),
        CheckConstraint("status IN ('confirmed', 'waitlisted', 'cancelled')", name="valid_status"),
        CheckConstraint("participation_no > 0", name="positive_participation_no"),
        CheckConstraint(
            "email = lower(btrim(email)) AND email <> ''",
            name="normalized_email",
        ),
        CheckConstraint(
            "(status = 'confirmed' AND ticket_code IS NOT NULL AND waitlist_seq IS NULL) OR "
            "(status = 'waitlisted' AND waitlist_seq IS NOT NULL AND waitlist_seq > 0 "
            "AND ticket_code IS NULL "
            "AND checked_in_at IS NULL) OR "
            "(status = 'cancelled' AND ticket_code IS NULL "
            "AND waitlist_seq IS NULL AND checked_in_at IS NULL)",
            name="consistent_state",
        ),
        CheckConstraint("ticket_code IS NULL OR length(ticket_code) > 0", name="nonempty_ticket"),
        CheckConstraint("length(manage_token_hash) > 0", name="nonempty_manage_token_hash"),
        Index("ix_registrations_event_status", "event_id", "status"),
        Index(
            "ix_registrations_waitlist",
            "event_id",
            "waitlist_seq",
            postgresql_where=text("status = 'waitlisted'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="RESTRICT"))
    email: Mapped[str] = mapped_column(Text)
    status: Mapped[RegistrationStatus] = mapped_column(
        Enum(
            RegistrationStatus,
            values_callable=lambda items: [item.value for item in items],
            native_enum=False,
            length=12,
            validate_strings=True,
        )
    )
    participation_no: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    waitlist_seq: Mapped[int | None] = mapped_column(BigInteger)
    ticket_code: Mapped[str | None] = mapped_column(Text, unique=True)
    manage_token_hash: Mapped[str] = mapped_column(Text, unique=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @validates("email")
    def normalize_email(self, _key: str, value: str) -> str:
        return value.strip().lower()


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('ticket', 'waitlist', 'reminder', 'rescheduled')", name="valid_kind"
        ),
        CheckConstraint(
            "status IN ('pending', 'forwarded', 'sent', 'cancelled', 'failed')", name="valid_status"
        ),
        CheckConstraint("attempts >= 0", name="nonnegative_attempts"),
        CheckConstraint("length(dedup_key) > 0", name="nonempty_dedup_key"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="object_payload"),
        CheckConstraint(
            "status NOT IN ('sent', 'forwarded') OR prepared_at IS NOT NULL",
            name="consistent_delivery_state",
        ),
        Index(
            "ix_email_outbox_pending",
            "available_at",
            "id",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    registration_id: Mapped[UUID] = mapped_column(
        ForeignKey("registrations.id", ondelete="RESTRICT")
    )
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(
            NotificationKind,
            values_callable=lambda items: [item.value for item in items],
            native_enum=False,
            length=12,
            validate_strings=True,
        )
    )
    dedup_key: Mapped[str] = mapped_column(Text, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(
            OutboxStatus,
            values_callable=lambda items: [item.value for item in items],
            native_enum=False,
            length=12,
            validate_strings=True,
        ),
        server_default=text("'pending'"),
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
