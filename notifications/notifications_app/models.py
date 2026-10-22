from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Integer, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationJob(Base):
    __tablename__ = "notification_jobs"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_jobs_object_payload"),
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_jobs_valid_status"),
        CheckConstraint("attempts >= 0", name="ck_jobs_nonnegative_attempts"),
        CheckConstraint("mime IS NULL OR octet_length(mime) > 0", name="ck_jobs_nonempty_mime"),
        CheckConstraint("status <> 'sent' OR mime IS NOT NULL", name="ck_jobs_sent_requires_mime"),
        Index("ix_jobs_pending", "available_at", "id", postgresql_where=text("status = 'pending'")),
    )

    # Future handover will supply the existing Core outbox UUID, never a new identity.
    id: Mapped[UUID] = mapped_column(primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    mime: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            values_callable=lambda items: [item.value for item in items],
            native_enum=False,
            length=12,
            validate_strings=True,
        ),
        server_default=text("'pending'"),
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    last_error: Mapped[str | None] = mapped_column(Text)
