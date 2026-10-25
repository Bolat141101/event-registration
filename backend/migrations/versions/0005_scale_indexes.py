"""Bounded event pages and outbox lookups by registration. No data/column changes."""

from alembic import op

revision = "0005_scale_indexes"
down_revision = "0004_canonical_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_events_start", "events", ["starts_at", "id"])
    op.create_index("ix_email_outbox_registration", "email_outbox", ["registration_id"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_registration", table_name="email_outbox")
    op.drop_index("ix_events_start", table_name="events")
