"""Execute the real administrative bootstrap only against Compose's tmpfs test-db."""

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

CORE_TABLES = ("alembic_version", "email_outbox", "events", "registrations")
NOTIFICATIONS_TABLES = ("alembic_version", "notification_jobs")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def run_command(*command: str, cwd: str, env: dict[str, str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *command, cwd=cwd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise
    assert process.returncode == 0, (stdout + stderr).decode()


def checked_test_urls() -> tuple[URL, URL]:
    core = make_url(os.environ["TEST_CORE_DATABASE_URL"])
    notifications = make_url(os.environ["TEST_NOTIFICATIONS_DATABASE_URL"])
    # Fail closed: this administrative test may never target the application server.
    assert os.environ["PGHOST"] == "test-db"
    assert os.environ["PGUSER"] == "events_test"
    for url, database, role, prefix in (
        (core, "event_registration_test", "core_app_test", "CORE"),
        (notifications, "event_notifications_test", "notifications_app_test", "NOTIFICATIONS"),
    ):
        assert url.drivername == "postgresql+asyncpg"
        assert url.host == "test-db" and url.port == 5432
        assert url.database == database and url.username == role
        assert os.environ[f"{prefix}_DB"] == database
        assert os.environ[f"{prefix}_USER"] == role
        assert os.environ[f"{prefix}_PASSWORD"] == url.password
    return core, notifications


async def bootstrap() -> None:
    environment = {"PATH": os.environ["PATH"]}
    for key in (
        "PGHOST",
        "PGUSER",
        "PGPASSWORD",
        "CORE_DB",
        "CORE_USER",
        "CORE_PASSWORD",
        "NOTIFICATIONS_DB",
        "NOTIFICATIONS_USER",
        "NOTIFICATIONS_PASSWORD",
    ):
        environment[key] = os.environ[key]
    await run_command("/bin/sh", "/bootstrap/bootstrap.sh", cwd="/bootstrap", env=environment)


@pytest.fixture
async def databases() -> AsyncIterator[tuple[AsyncEngine, AsyncEngine]]:
    core_url, notifications_url = checked_test_urls()
    await bootstrap()
    for url, directory in ((core_url, "/app"), (notifications_url, "/notifications")):
        # Migrations also run as their ordinary owner, without admin credentials.
        environment = {
            "PATH": os.environ["PATH"],
            "PYTHONDONTWRITEBYTECODE": "1",
            "DATABASE_URL": url.render_as_string(hide_password=False),
            "ORGANIZER_TOKEN": "test_organizer_token_32_characters_minimum",
        }
        await run_command(
            sys.executable, "-m", "alembic", "upgrade", "head", cwd=directory, env=environment
        )
    engines = tuple(
        create_async_engine(url, isolation_level="READ COMMITTED", hide_parameters=True)
        for url in (core_url, notifications_url)
    )
    try:
        yield engines[0], engines[1]
    finally:
        for engine in engines:
            await engine.dispose()


async def data_snapshot(
    engine: AsyncEngine, tables: tuple[str, ...]
) -> dict[str, list[tuple[Any, ...]]]:
    async with engine.connect() as connection:
        return {
            table: [
                tuple(row)
                for row in await connection.execute(
                    text(f'SELECT * FROM public."{table}" ORDER BY 1')
                )
            ]
            for table in tables
        }


async def assert_permissions(
    engine: AsyncEngine, other_database: str, tables: tuple[str, ...]
) -> dict[str, list[tuple[Any, ...]]]:
    queries = {
        "database": "SELECT datname, pg_get_userbyid(datdba), datacl::text "
        "FROM pg_database WHERE datname = current_database()",
        "schema": "SELECT nspname, pg_get_userbyid(nspowner), nspacl::text "
        "FROM pg_namespace WHERE nspname = 'public'",
        "objects": "SELECT c.relname, c.relkind::text, pg_get_userbyid(c.relowner), c.relacl::text "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' ORDER BY c.relname",
        "indexes": "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = 'public' ORDER BY indexname",
        "constraints": "SELECT c.conname, pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname = 'public' ORDER BY c.conname",
    }
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT current_user")) == engine.url.username
        assert await connection.scalar(text("SHOW transaction_isolation")) == "read committed"
        assert await connection.scalar(
            text(
                "SELECT NOT (rolsuper OR rolcreatedb OR rolcreaterole "
                "OR rolreplication OR rolbypassrls "
                "OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid)) "
                "FROM pg_roles r WHERE rolname = current_user"
            )
        )
        assert await connection.scalar(
            text(
                "SELECT has_database_privilege(current_database(), 'CONNECT') "
                "AND has_database_privilege(current_database(), 'CREATE') "
                "AND has_database_privilege(current_database(), 'TEMPORARY') "
                "AND has_schema_privilege('public', 'USAGE') "
                "AND has_schema_privilege('public', 'CREATE')"
            )
        )
        for privilege in ("CONNECT", "CREATE", "TEMPORARY"):
            assert not await connection.scalar(
                text("SELECT has_database_privilege(:database, :privilege)"),
                {"database": other_database, "privilege": privilege},
            )
        assert not await connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_database d, "
                "aclexplode(COALESCE(d.datacl, acldefault('d', d.datdba))) a "
                "WHERE d.datname = current_database() AND a.grantee = 0)"
            )
        )
        assert not await connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_namespace n, aclexplode(n.nspacl) a "
                "WHERE n.nspname = 'public' AND a.grantee = 0)"
            )
        )
        for table in tables:
            for privilege in (
                "SELECT",
                "INSERT",
                "UPDATE",
                "DELETE",
                "TRUNCATE",
                "REFERENCES",
                "TRIGGER",
            ):
                assert await connection.scalar(
                    text("SELECT has_table_privilege(:table, :privilege)"),
                    {"table": f"public.{table}", "privilege": privilege},
                )
        snapshot = {
            name: [tuple(row) for row in await connection.execute(text(query))]
            for name, query in queries.items()
        }
    assert snapshot["database"][0][1] == engine.url.username
    assert snapshot["schema"][0][1] == engine.url.username
    assert {row[0] for row in snapshot["objects"] if row[1] == "r"} == set(tables)
    assert all(row[2] == engine.url.username for row in snapshot["objects"])
    return snapshot


async def assert_cross_database_denied(source: AsyncEngine, target: AsyncEngine) -> None:
    foreign = create_async_engine(
        source.url.set(database=target.url.database), hide_parameters=True
    )
    try:
        # asyncpg may expose a raw driver exception during connect. Verify SQLSTATE,
        # so a network failure or any unrelated exception cannot satisfy this test.
        with pytest.raises(Exception) as error:
            async with foreign.connect() as connection:
                await connection.execute(text("SELECT 1"))
        underlying = getattr(error.value, "orig", error.value)
        assert getattr(underlying, "sqlstate", None) == "42501"
    finally:
        await foreign.dispose()


async def seed(
    core: AsyncEngine, notifications: AsyncEngine, event_id: UUID, ids: list[UUID]
) -> None:
    now = datetime.now(UTC)
    async with core.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO events (id, description, starts_at, capacity, schedule_version) "
                "VALUES (:id, 'Bootstrap regression — сохранность', :now, 1, 3)"
            ),
            {"id": event_id, "now": now},
        )
        for index, (identity, status) in enumerate(
            zip(ids, ("confirmed", "waitlisted", "cancelled"), strict=True)
        ):
            await connection.execute(
                text(
                    "INSERT INTO registrations "
                    "(id, event_id, email, status, participation_no, waitlist_seq, ticket_code, "
                    "manage_token_hash, checked_in_at) "
                    "VALUES (:id, :event, :email, :status, 2, :seq, :ticket, :hash, :checkin)"
                ),
                {
                    "id": identity,
                    "event": event_id,
                    "email": f"{identity}@example.test",
                    "status": status,
                    "seq": 7 if status == "waitlisted" else None,
                    "ticket": str(identity) if status == "confirmed" else None,
                    "hash": f"hash-{identity}",
                    "checkin": now if status == "confirmed" else None,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO email_outbox "
                    "(id, registration_id, kind, dedup_key, payload, prepared_at, available_at, "
                    "status, attempts, last_error) "
                    "VALUES (:id, :id, 'ticket', :key, :payload, :now, :now, "
                    ":status, :attempts, :error)"
                ),
                {
                    "id": identity,
                    "key": f"bootstrap:{identity}",
                    "payload": json.dumps({"registration_id": str(identity)}),
                    "now": now,
                    "status": ("sent", "pending", "failed")[index],
                    "attempts": index + 1,
                    "error": "SMTP timeout" if index == 2 else None,
                },
            )
    async with notifications.begin() as connection:
        for index, identity in enumerate(ids):
            await connection.execute(
                text(
                    "INSERT INTO notification_jobs "
                    "(id, payload, mime, status, attempts, available_at, last_error) "
                    "VALUES (:id, :payload, :mime, :status, :attempts, :now, :error)"
                ),
                {
                    "id": identity,
                    "payload": json.dumps({"registration_id": str(identity)}),
                    "mime": f"Message-ID: <{identity}@example.test>\r\n\r\nBody\r\n".encode()
                    if index != 1
                    else None,
                    "status": ("sent", "pending", "failed")[index],
                    "attempts": index + 1,
                    "now": now,
                    "error": "SMTP timeout" if index == 2 else None,
                },
            )


async def test_repeated_bootstrap_preserves_data_ownership_permissions_and_isolation(
    databases: tuple[AsyncEngine, AsyncEngine],
) -> None:
    core, notifications = databases
    event_id, identities = uuid4(), [uuid4() for _ in range(3)]
    try:
        await seed(core, notifications, event_id, identities)
        core_rows = await data_snapshot(core, CORE_TABLES)
        notification_rows = await data_snapshot(notifications, NOTIFICATIONS_TABLES)
        core_security = await assert_permissions(core, "event_notifications_test", CORE_TABLES)
        notification_security = await assert_permissions(
            notifications, "event_registration_test", NOTIFICATIONS_TABLES
        )
        for _ in range(2):
            await assert_cross_database_denied(core, notifications)
            await assert_cross_database_denied(notifications, core)
            await bootstrap()
            assert await data_snapshot(core, CORE_TABLES) == core_rows
            assert await data_snapshot(notifications, NOTIFICATIONS_TABLES) == notification_rows
            assert (
                await assert_permissions(core, "event_notifications_test", CORE_TABLES)
                == core_security
            )
            assert (
                await assert_permissions(
                    notifications, "event_registration_test", NOTIFICATIONS_TABLES
                )
                == notification_security
            )
        await assert_cross_database_denied(core, notifications)
        await assert_cross_database_denied(notifications, core)
    finally:
        # Remove only this test's UUIDs; never truncate databases shared with other suites.
        async with core.begin() as connection:
            await connection.execute(
                text(
                    "DELETE FROM email_outbox WHERE registration_id IN "
                    "(SELECT id FROM registrations WHERE event_id = :id)"
                ),
                {"id": event_id},
            )
            await connection.execute(
                text("DELETE FROM registrations WHERE event_id = :id"), {"id": event_id}
            )
            await connection.execute(text("DELETE FROM events WHERE id = :id"), {"id": event_id})
        async with notifications.begin() as connection:
            for identity in identities:
                await connection.execute(
                    text("DELETE FROM notification_jobs WHERE id = :id"), {"id": identity}
                )
