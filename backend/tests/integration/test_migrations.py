import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from app.db.health import database_is_ready, expected_schema_heads

pytestmark = pytest.mark.integration


def test_migration_round_trip(integration_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.downgrade(config, "0001_initial_schema")
    assert (
        sum(
            len(inspect(integration_engine).get_columns(table))
            for table in ("events", "registrations", "email_outbox")
        )
        == 34
    )
    command.downgrade(config, "base")
    assert not {"events", "registrations", "email_outbox"} & set(
        inspect(integration_engine).get_table_names()
    )
    assert not database_is_ready(integration_engine, expected_schema_heads())
    command.upgrade(config, "head")
    assert {"events", "registrations", "email_outbox"} <= set(
        inspect(integration_engine).get_table_names()
    )
    command.check(config)


def test_upgrade_preserves_data_and_blocks_lossy_downgrade(
    integration_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    event_id, confirmed_id, waiting_id, cancelled_id, message_id = [uuid4() for _ in range(5)]
    timestamp = datetime(2026, 10, 21, 12, tzinfo=UTC)
    try:
        command.downgrade(config, "0001_initial_schema")
        with integration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO events "
                    "(id, title, description, starts_at, capacity, "
                    "next_waitlist_seq, schedule_version) "
                    "VALUES (:id, 'Historical title', 'Description', :time, 1, 100, 3)"
                ),
                {"id": event_id, "time": timestamp},
            )
            connection.execute(
                text(
                    "INSERT INTO registrations "
                    "(id, event_id, email, email_normalized, status, participation_no, "
                    "waitlist_seq, ticket_code, manage_token_hash, checked_in_at, cancelled_at) "
                    "VALUES (:id, :event_id, :email, lower(btrim(:email)), :status, 2, "
                    ":seq, :ticket, :hash, :checked, :cancelled)"
                ),
                [
                    {
                        "id": reg_id,
                        "event_id": event_id,
                        "email": email,
                        "status": status,
                        "seq": seq,
                        "ticket": ticket,
                        "hash": f"hash-{reg_id}",
                        "checked": timestamp if status == "confirmed" else None,
                        "cancelled": timestamp if status == "cancelled" else None,
                    }
                    for reg_id, email, status, seq, ticket in [
                        (confirmed_id, " USER@Example.test ", "confirmed", None, "stable-ticket"),
                        (waiting_id, " Wait@Example.test ", "waitlisted", 7, None),
                        (cancelled_id, " Cancel@Example.test ", "cancelled", None, None),
                    ]
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO email_outbox "
                    "(id, registration_id, kind, dedup_key, payload, prepared_at, available_at, "
                    "status, attempts, sent_at, last_error) "
                    "VALUES (:id, :reg, 'ticket', :key, "
                    '\'{"mime": "frozen message", "participation_no": 2}\'::jsonb, '
                    ":time, :time, 'sent', 2, :time, 'previous transient error')"
                ),
                {
                    "id": message_id,
                    "reg": confirmed_id,
                    "key": f"ticket:{confirmed_id}:2",
                    "time": timestamp,
                },
            )
        command.upgrade(config, "head")
        command.check(config)
        with integration_engine.connect() as connection:
            item = connection.execute(text("SELECT * FROM events")).mappings().one()
            assert item["id"] == event_id
            assert item["schedule_version"] == 3
            entries = {
                row["id"]: row
                for row in connection.execute(text("SELECT * FROM registrations")).mappings()
            }
            assert entries[confirmed_id]["email"] == "user@example.test"
            assert entries[waiting_id]["email"] == "wait@example.test"
            assert entries[cancelled_id]["email"] == "cancel@example.test"
            assert entries[confirmed_id]["ticket_code"] == "stable-ticket"
            assert entries[confirmed_id]["checked_in_at"] == timestamp
            assert entries[confirmed_id]["participation_no"] == 2
            assert entries[confirmed_id]["manage_token_hash"] == f"hash-{confirmed_id}"
            assert entries[waiting_id]["waitlist_seq"] == 7
            assert entries[cancelled_id]["status"] == "cancelled"
            message = connection.execute(text("SELECT * FROM email_outbox")).mappings().one()
            assert message["id"] == message_id
            assert message["registration_id"] == confirmed_id
            assert message["dedup_key"] == f"ticket:{confirmed_id}:2"
            assert message["payload"] == {"mime": "frozen message", "participation_no": 2}
            assert message["prepared_at"] == timestamp
            assert message["available_at"] == timestamp
            assert message["status"] == "sent"
            assert message["attempts"] == 2
            assert message["last_error"] == "previous transient error"
        with pytest.raises(RuntimeError, match="requires empty domain tables"):
            command.downgrade(config, "0001_initial_schema")
        assert database_is_ready(integration_engine, expected_schema_heads())
        assert len(inspect(integration_engine).get_columns("events")) == 5
    finally:
        # integration_engine only permits a dedicated database ending in _test.
        with integration_engine.begin() as connection:
            connection.execute(text("TRUNCATE email_outbox, registrations, events"))
        command.upgrade(config, "head")
