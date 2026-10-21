"""Reduce the three domain tables from 34 to 24 columns.

Upgrade preserves identities, normalized addresses, versions and outbox payloads.
Discarded titles/audit dates cannot be reconstructed. Downgrade therefore requires
empty domain tables; recover a populated pre-upgrade database from its backup.

Revision ID: 0002_simplify_schema
Revises: 0001_initial_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_simplify_schema"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_events_nonnegative_waitlist_seq"), "events", type_="check")
    op.drop_constraint(op.f("ck_events_nonempty_title"), "events", type_="check")
    for column in ("title", "next_waitlist_seq", "created_at", "updated_at"):
        op.drop_column("events", column)

    op.drop_constraint("uq_registrations_event_email", "registrations", type_="unique")
    op.drop_constraint(op.f("ck_registrations_normalized_email"), "registrations", type_="check")
    op.drop_constraint(op.f("ck_registrations_consistent_state"), "registrations", type_="check")
    # The previous CHECK ties this value to lower(btrim(email)); uniqueness is preserved.
    op.execute("UPDATE registrations SET email = email_normalized")
    for column in ("email_normalized", "cancelled_at", "created_at", "updated_at"):
        op.drop_column("registrations", column)
    op.create_unique_constraint(
        "uq_registrations_event_email", "registrations", ["event_id", "email"]
    )
    op.create_check_constraint(
        op.f("ck_registrations_normalized_email"),
        "registrations",
        "email = lower(btrim(email)) AND email <> ''",
    )
    op.create_check_constraint(
        op.f("ck_registrations_consistent_state"),
        "registrations",
        "(status = 'confirmed' AND ticket_code IS NOT NULL AND waitlist_seq IS NULL) OR "
        "(status = 'waitlisted' AND waitlist_seq IS NOT NULL AND waitlist_seq > 0 "
        "AND ticket_code IS NULL AND checked_in_at IS NULL) OR "
        "(status = 'cancelled' AND ticket_code IS NULL "
        "AND waitlist_seq IS NULL AND checked_in_at IS NULL)",
    )

    op.drop_constraint(
        op.f("ck_email_outbox_consistent_delivery_state"), "email_outbox", type_="check"
    )
    op.drop_column("email_outbox", "sent_at")
    op.drop_column("email_outbox", "created_at")
    op.create_check_constraint(
        op.f("ck_email_outbox_consistent_delivery_state"),
        "email_outbox",
        "status <> 'sent' OR prepared_at IS NOT NULL",
    )


def downgrade() -> None:
    # Block concurrent writers as well as checking existing rows before any DDL.
    op.execute("LOCK TABLE events, registrations, email_outbox IN ACCESS EXCLUSIVE MODE")
    has_data = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM events UNION ALL "
            "SELECT 1 FROM registrations UNION ALL SELECT 1 FROM email_outbox)"
        )
    )
    if has_data:
        raise RuntimeError(
            "0002 downgrade requires empty domain tables: discarded titles and audit dates "
            "cannot be recovered. Restore the pre-upgrade database backup instead."
        )

    op.drop_constraint(
        op.f("ck_email_outbox_consistent_delivery_state"), "email_outbox", type_="check"
    )
    op.add_column("email_outbox", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "email_outbox",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_check_constraint(
        op.f("ck_email_outbox_consistent_delivery_state"),
        "email_outbox",
        "(status = 'sent' AND sent_at IS NOT NULL AND prepared_at IS NOT NULL) OR "
        "(status <> 'sent' AND sent_at IS NULL)",
    )

    op.drop_constraint("uq_registrations_event_email", "registrations", type_="unique")
    op.drop_constraint(op.f("ck_registrations_normalized_email"), "registrations", type_="check")
    op.drop_constraint(op.f("ck_registrations_consistent_state"), "registrations", type_="check")
    op.add_column("registrations", sa.Column("email_normalized", sa.Text(), nullable=False))
    op.add_column(
        "registrations", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
    )
    for column in ("created_at", "updated_at"):
        op.add_column(
            "registrations",
            sa.Column(
                column, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
        )
    op.create_unique_constraint(
        "uq_registrations_event_email", "registrations", ["event_id", "email_normalized"]
    )
    op.create_check_constraint(
        op.f("ck_registrations_normalized_email"),
        "registrations",
        "email_normalized = lower(btrim(email)) AND email_normalized <> ''",
    )
    op.create_check_constraint(
        op.f("ck_registrations_consistent_state"),
        "registrations",
        "(status = 'confirmed' AND ticket_code IS NOT NULL AND waitlist_seq IS NULL "
        "AND cancelled_at IS NULL) OR "
        "(status = 'waitlisted' AND waitlist_seq IS NOT NULL AND waitlist_seq > 0 "
        "AND ticket_code IS NULL AND checked_in_at IS NULL AND cancelled_at IS NULL) OR "
        "(status = 'cancelled' AND cancelled_at IS NOT NULL AND ticket_code IS NULL "
        "AND waitlist_seq IS NULL AND checked_in_at IS NULL)",
    )

    op.add_column("events", sa.Column("title", sa.Text(), nullable=False))
    op.add_column(
        "events",
        sa.Column(
            "next_waitlist_seq", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
    )
    for column in ("created_at", "updated_at"):
        op.add_column(
            "events",
            sa.Column(
                column, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
        )
    op.create_check_constraint(
        op.f("ck_events_nonnegative_waitlist_seq"), "events", "next_waitlist_seq >= 0"
    )
    op.create_check_constraint(
        op.f("ck_events_nonempty_title"), "events", "length(btrim(title)) > 0"
    )
