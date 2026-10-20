"""Create events, registrations and the single-worker email outbox.

Revision ID: 0001_initial_schema
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column(
            "next_waitlist_seq", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("schedule_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("capacity > 0", name=op.f("ck_events_positive_capacity")),
        sa.CheckConstraint(
            "next_waitlist_seq >= 0", name=op.f("ck_events_nonnegative_waitlist_seq")
        ),
        sa.CheckConstraint(
            "schedule_version > 0", name=op.f("ck_events_positive_schedule_version")
        ),
        sa.CheckConstraint("length(btrim(title)) > 0", name=op.f("ck_events_nonempty_title")),
        sa.CheckConstraint(
            "length(btrim(description)) > 0", name=op.f("ck_events_nonempty_description")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_table(
        "registrations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_normalized", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("participation_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("waitlist_seq", sa.BigInteger(), nullable=True),
        sa.Column("ticket_code", sa.Text(), nullable=True),
        sa.Column("manage_token_hash", sa.Text(), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('confirmed', 'waitlisted', 'cancelled')",
            name=op.f("ck_registrations_valid_status"),
        ),
        sa.CheckConstraint(
            "participation_no > 0", name=op.f("ck_registrations_positive_participation_no")
        ),
        sa.CheckConstraint(
            "email_normalized = lower(btrim(email)) AND email_normalized <> ''",
            name=op.f("ck_registrations_normalized_email"),
        ),
        sa.CheckConstraint(
            "(status = 'confirmed' AND ticket_code IS NOT NULL AND waitlist_seq IS NULL "
            "AND cancelled_at IS NULL) OR "
            "(status = 'waitlisted' AND waitlist_seq IS NOT NULL AND waitlist_seq > 0 "
            "AND ticket_code IS NULL AND checked_in_at IS NULL AND cancelled_at IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL AND ticket_code IS NULL "
            "AND waitlist_seq IS NULL AND checked_in_at IS NULL)",
            name=op.f("ck_registrations_consistent_state"),
        ),
        sa.CheckConstraint(
            "ticket_code IS NULL OR length(ticket_code) > 0",
            name=op.f("ck_registrations_nonempty_ticket"),
        ),
        sa.CheckConstraint(
            "length(manage_token_hash) > 0",
            name=op.f("ck_registrations_nonempty_manage_token_hash"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_registrations_event_id_events"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registrations")),
        sa.UniqueConstraint("event_id", "email_normalized", name="uq_registrations_event_email"),
        sa.UniqueConstraint("event_id", "waitlist_seq", name="uq_registrations_event_waitlist_seq"),
        sa.UniqueConstraint("ticket_code", name=op.f("uq_registrations_ticket_code")),
        sa.UniqueConstraint("manage_token_hash", name=op.f("uq_registrations_manage_token_hash")),
    )
    op.create_index("ix_registrations_event_status", "registrations", ["event_id", "status"])
    op.create_index(
        "ix_registrations_waitlist",
        "registrations",
        ["event_id", "waitlist_seq"],
        postgresql_where=sa.text("status = 'waitlisted'"),
    )
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("registration_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('ticket', 'waitlist', 'reminder', 'rescheduled')",
            name=op.f("ck_email_outbox_valid_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'cancelled', 'failed')",
            name=op.f("ck_email_outbox_valid_status"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_email_outbox_nonnegative_attempts")),
        sa.CheckConstraint(
            "length(dedup_key) > 0", name=op.f("ck_email_outbox_nonempty_dedup_key")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name=op.f("ck_email_outbox_object_payload")
        ),
        sa.CheckConstraint(
            "(status = 'sent' AND sent_at IS NOT NULL AND prepared_at IS NOT NULL) OR "
            "(status <> 'sent' AND sent_at IS NULL)",
            name=op.f("ck_email_outbox_consistent_delivery_state"),
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["registrations.id"],
            name=op.f("fk_email_outbox_registration_id_registrations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_outbox")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_email_outbox_dedup_key")),
    )
    op.create_index(
        "ix_email_outbox_pending",
        "email_outbox",
        ["available_at", "id"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_pending", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_index("ix_registrations_waitlist", table_name="registrations")
    op.drop_index("ix_registrations_event_status", table_name="registrations")
    op.drop_table("registrations")
    op.drop_table("events")
