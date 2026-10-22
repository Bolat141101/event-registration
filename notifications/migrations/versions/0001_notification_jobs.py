"""Create infrastructure storage for future notification delivery.

Revision ID: 0001_notification_jobs
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_notification_jobs"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mime", sa.LargeBinary(), nullable=True),
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_jobs_object_payload"),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_jobs_valid_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_jobs_nonnegative_attempts"),
        sa.CheckConstraint("mime IS NULL OR octet_length(mime) > 0", name="ck_jobs_nonempty_mime"),
        sa.CheckConstraint(
            "status <> 'sent' OR mime IS NOT NULL", name="ck_jobs_sent_requires_mime"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jobs_pending",
        "notification_jobs",
        ["available_at", "id"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.execute("LOCK TABLE notification_jobs IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM notification_jobs)")):
        raise RuntimeError(
            "Notifications downgrade requires empty notification_jobs; "
            "restore a backup for data recovery"
        )
    op.drop_index("ix_jobs_pending", table_name="notification_jobs")
    op.drop_table("notification_jobs")
