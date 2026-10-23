"""Separate HTTP acceptance from SMTP delivery without changing existing rows.

Revision ID: 0003_outbox_forwarded
Revises: 0002_simplify_schema
"""

from alembic import op
from sqlalchemy import text

revision = "0003_outbox_forwarded"
down_revision = "0002_simplify_schema"
branch_labels = None
depends_on = None


def replace_checks(statuses: str, prepared: str) -> None:
    for name in ("valid_status", "consistent_delivery_state"):
        op.drop_constraint(op.f(f"ck_email_outbox_{name}"), "email_outbox", type_="check")
    op.create_check_constraint(op.f("ck_email_outbox_valid_status"), "email_outbox", statuses)
    op.create_check_constraint(
        op.f("ck_email_outbox_consistent_delivery_state"), "email_outbox", prepared
    )


def upgrade() -> None:
    replace_checks(
        "status IN ('pending', 'forwarded', 'sent', 'cancelled', 'failed')",
        "status NOT IN ('sent', 'forwarded') OR prepared_at IS NOT NULL",
    )


def downgrade() -> None:
    op.execute("LOCK TABLE email_outbox IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(
        text("SELECT EXISTS (SELECT 1 FROM email_outbox WHERE status='forwarded')")
    ):
        raise RuntimeError(
            "Cannot downgrade while forwarded jobs exist; HTTP acceptance is not sent"
        )
    replace_checks(
        "status IN ('pending', 'sent', 'cancelled', 'failed')",
        "status <> 'sent' OR prepared_at IS NOT NULL",
    )
