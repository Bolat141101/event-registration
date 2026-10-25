import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.health import database_is_ready, expected_schema_heads
from app.db.models import EmailOutbox, Event, Registration

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def migrate(
    engine: AsyncEngine, operation: Callable[..., None], config: Config, *args: str
) -> None:
    # Alembic's public command is sync and owns asyncio.run in env.py. Only this test
    # harness uses a thread; SQL itself still runs through asyncpg, never psycopg.
    await engine.dispose()  # DDL from another engine invalidates asyncpg's prepared cache.
    try:
        await asyncio.to_thread(operation, config, *args)
    finally:
        await engine.dispose()


async def table_names(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda sync: inspect(sync).get_table_names())


async def column_count(engine: AsyncEngine, *tables: str) -> int:
    async with engine.connect() as connection:
        return await connection.run_sync(
            lambda sync: sum(len(inspect(sync).get_columns(table)) for table in tables)
        )


async def test_scale_indexes_preserve_populated_tables(
    integration_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    event_id, registration_id, message_id = [uuid4() for _ in range(3)]
    timestamp = datetime(2026, 10, 25, 12, tzinfo=UTC)
    indexes = {"ix_events_start", "ix_email_outbox_registration"}

    async def snapshot() -> list[str]:
        async with integration_engine.connect() as connection:
            return [
                str(
                    await connection.scalar(
                        text(
                            "SELECT md5(jsonb_agg(to_jsonb(t) ORDER BY id)::text) "
                            f"FROM {table} AS t"
                        )
                    )
                )
                for table in ("events", "registrations", "email_outbox")
            ]

    async def present_indexes() -> set[str]:
        async with integration_engine.connect() as connection:
            return set(
                (await connection.execute(text("SELECT indexname FROM pg_indexes"))).scalars()
            )

    try:
        async with integration_engine.begin() as connection:
            await connection.execute(
                Event.__table__.insert(),
                dict(id=event_id, description="Migration fixture", starts_at=timestamp, capacity=1),
            )
            await connection.execute(
                Registration.__table__.insert(),
                dict(
                    id=registration_id,
                    event_id=event_id,
                    email="migration@example.test",
                    status="confirmed",
                    ticket_code=f"ticket-{registration_id}",
                    manage_token_hash=f"hash-{registration_id}",
                    checked_in_at=timestamp,
                ),
            )
            await connection.execute(
                EmailOutbox.__table__.insert(),
                dict(
                    id=message_id,
                    registration_id=registration_id,
                    kind="ticket",
                    dedup_key=f"ticket:{registration_id}:1",
                    payload={"frozen": "payload", "participation_no": 1},
                    prepared_at=timestamp,
                    available_at=timestamp,
                    status="forwarded",
                    attempts=2,
                ),
            )
        before = await snapshot()
        assert indexes <= await present_indexes()
        await migrate(integration_engine, command.downgrade, config, "0004_canonical_email")
        assert not indexes & await present_indexes()
        assert await snapshot() == before
        await migrate(integration_engine, command.upgrade, config, "head")
        assert indexes <= await present_indexes()
        assert await snapshot() == before
        assert (
            await column_count(integration_engine, "events", "registrations", "email_outbox") == 24
        )
        await migrate(integration_engine, command.check, config)
    finally:
        await migrate(integration_engine, command.upgrade, config, "head")
        async with integration_engine.begin() as connection:
            await connection.execute(
                EmailOutbox.__table__.delete().where(EmailOutbox.id == message_id)
            )
            await connection.execute(
                Registration.__table__.delete().where(Registration.id == registration_id)
            )
            await connection.execute(Event.__table__.delete().where(Event.id == event_id))


async def test_migration_round_trip(
    integration_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    await migrate(integration_engine, command.downgrade, config, "0001_initial_schema")
    assert await column_count(integration_engine, "events", "registrations", "email_outbox") == 34
    await migrate(integration_engine, command.downgrade, config, "base")
    assert not {"events", "registrations", "email_outbox"} & set(
        await table_names(integration_engine)
    )
    assert not (await database_is_ready(integration_engine, expected_schema_heads()))
    await migrate(integration_engine, command.upgrade, config, "head")
    assert {"events", "registrations", "email_outbox"} <= set(await table_names(integration_engine))
    await migrate(integration_engine, command.check, config)


async def test_upgrade_preserves_data_and_blocks_lossy_downgrade(
    integration_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    event_id, confirmed_id, waiting_id, cancelled_id, message_id = [uuid4() for _ in range(5)]
    timestamp = datetime(2026, 10, 21, 12, tzinfo=UTC)
    try:
        await migrate(integration_engine, command.downgrade, config, "0001_initial_schema")
        async with integration_engine.begin() as connection:
            (
                await connection.execute(
                    text(
                        "INSERT INTO events "
                        "(id, title, description, starts_at, capacity, "
                        "next_waitlist_seq, schedule_version) "
                        "VALUES (:id, 'Historical title', 'Description', :time, 1, 100, 3)"
                    ),
                    {"id": event_id, "time": timestamp},
                )
            )
            (
                await connection.execute(
                    text(
                        "INSERT INTO registrations "
                        "(id, event_id, email, email_normalized, status, participation_no, "
                        "waitlist_seq, ticket_code, manage_token_hash, "
                        "checked_in_at, cancelled_at) "
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
                            (
                                confirmed_id,
                                " USER@Example.test ",
                                "confirmed",
                                None,
                                "stable-ticket",
                            ),
                            (waiting_id, " Wait@Example.test ", "waitlisted", 7, None),
                            (cancelled_id, " Cancel@Example.test ", "cancelled", None, None),
                        ]
                    ],
                )
            )
            (
                await connection.execute(
                    text(
                        "INSERT INTO email_outbox "
                        "(id, registration_id, kind, dedup_key, payload, "
                        "prepared_at, available_at, "
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
            )
        await migrate(integration_engine, command.upgrade, config, "head")
        await migrate(integration_engine, command.check, config)
        async with integration_engine.connect() as connection:
            item = (await connection.execute(text("SELECT * FROM events"))).mappings().one()
            assert item["id"] == event_id
            assert item["schedule_version"] == 3
            entries = {
                row["id"]: row
                for row in (
                    await connection.execute(text("SELECT * FROM registrations"))
                ).mappings()
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
            message = (
                (await connection.execute(text("SELECT * FROM email_outbox"))).mappings().one()
            )
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
            await migrate(integration_engine, command.downgrade, config, "0001_initial_schema")
        assert await database_is_ready(integration_engine, expected_schema_heads())
        assert await column_count(integration_engine, "events") == 5
    finally:
        # integration_engine only permits a dedicated database ending in _test.
        async with integration_engine.begin() as connection:
            await connection.execute(text("TRUNCATE email_outbox, registrations, events"))
        await migrate(integration_engine, command.upgrade, config, "head")
