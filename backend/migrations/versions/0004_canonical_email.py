"""Canonicalize registration identity after an atomic collision preflight.

Never merge registrations or rewrite immutable outbox data. Downgrade relaxes
storage validation but cannot recover the former Unicode spelling of addresses.

Revision ID: 0004_canonical_email
Revises: 0003_outbox_forwarded
"""

from collections import defaultdict

from alembic import op
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import text

revision = "0004_canonical_email"
down_revision = "0003_outbox_forwarded"
branch_labels = None
depends_on = None


def canonical_v1(value: str) -> str:
    # Frozen policy for this data migration; independent of future app helpers.
    if any(character in value for character in "\r\n\x00"):
        raise ValueError("Invalid legacy email")
    try:
        address = validate_email(
            value.strip().lower(),
            check_deliverability=False,
            test_environment=True,
            allow_smtputf8=False,
        ).ascii_email
    except EmailNotValidError:
        raise ValueError("Invalid legacy email") from None
    if address is None:
        raise ValueError("ASCII email required")
    return address.lower()


def replace_check(ascii_only: bool) -> None:
    op.drop_constraint(op.f("ck_registrations_normalized_email"), "registrations", type_="check")
    condition = "email = lower(btrim(email)) AND email <> ''"
    if ascii_only:
        condition += " AND octet_length(email) = char_length(email)"
    op.create_check_constraint(
        op.f("ck_registrations_normalized_email"), "registrations", condition
    )


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("0004 requires an online collision preflight")
    # Order matches business operations. No writer can change the audited rows
    # between the preflight and UPDATE; outbox payloads are never updated here.
    op.execute("LOCK TABLE events, registrations IN ACCESS EXCLUSIVE MODE")
    connection = op.get_bind()
    rows = connection.execute(text("SELECT id,event_id,email FROM registrations ORDER BY id")).all()
    groups: dict[tuple[object, str], list[str]] = defaultdict(list)
    changes = []
    invalid = []
    for identity, event, address in rows:
        try:
            canonical = canonical_v1(address)
        except ValueError:
            invalid.append(str(identity))
            continue
        groups[(event, canonical)].append(str(identity))
        if address != canonical:
            changes.append({"identity": identity, "address": canonical})
    collisions = [ids for ids in groups.values() if len(ids) > 1]
    if invalid or collisions:
        # IDs only; no recipient addresses or tokens in Alembic logs.
        raise RuntimeError(
            f"Email canonicalization preflight failed; invalid IDs={invalid}; "
            f"collision registration IDs={collisions}; no rows changed"
        )
    if changes:
        connection.execute(
            text("UPDATE registrations SET email=:address WHERE id=:identity"), changes
        )
    replace_check(True)


def downgrade() -> None:
    op.execute("LOCK TABLE events, registrations IN ACCESS EXCLUSIVE MODE")
    replace_check(False)
    # Keep canonical identities. Original spelling was not stored and is not
    # recoverable by guessing; restore a pre-upgrade backup if it is required.
