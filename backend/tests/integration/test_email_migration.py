import os
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.email_audit import audit
from tests.integration.test_migrations import migrate

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PREVIOUS = "0003_outbox_forwarded"


async def legacy_rows(engine: AsyncEngine, event: UUID, addresses: list[str]) -> list[UUID]:
    identities = [uuid4() for _ in addresses]
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO events (id,description,starts_at,capacity) "
                "VALUES (:id,'legacy',now()+interval '2 days',10)"
            ),
            {"id": event},
        )
        await connection.execute(
            text(
                "INSERT INTO registrations "
                "(id,event_id,email,status,ticket_code,manage_token_hash) "
                "VALUES (:id,:event,:email,'confirmed',:ticket,:token)"
            ),
            [
                {
                    "id": identity,
                    "event": event,
                    "email": address,
                    "ticket": str(identity),
                    "token": str(identity),
                }
                for identity, address in zip(identities, addresses, strict=True)
            ],
        )
    return identities


async def snapshot(engine: AsyncEngine, table: str) -> list[tuple[object, ...]]:
    assert table in ("registrations", "email_outbox")
    async with engine.connect() as connection:
        return [
            tuple(row)
            for row in await connection.execute(text(f"SELECT * FROM {table} ORDER BY id"))
        ]


async def cleanup(engine: AsyncEngine, config: Config) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE email_outbox,registrations,events"))
    await migrate(engine, command.upgrade, config, "head")


async def test_upgrade_preserves_identity_and_payload_and_downgrade_keeps_canonical_data(
    integration_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    event = uuid4()
    try:
        await migrate(integration_engine, command.downgrade, config, PREVIOUS)
        identities = await legacy_rows(
            integration_engine, event, ["user@faß.de", "user@fass.de", "some.one+tag@example.test"]
        )
        other = uuid4()
        await legacy_rows(integration_engine, other, ["user@xn--fa-hia.de"])
        async with integration_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO email_outbox "
                    "(id,registration_id,kind,dedup_key,payload,prepared_at,status,available_at) "
                    "VALUES (:id,:reg,'ticket',:key,CAST(:payload AS jsonb),"
                    "now(),'forwarded',now())"
                ),
                {
                    "id": uuid4(),
                    "reg": identities[0],
                    "key": "legacy-frozen",
                    "payload": '{"recipient":"user@faß.de","frozen":true}',
                },
            )
        before = await snapshot(integration_engine, "registrations")
        messages = deepcopy(await snapshot(integration_engine, "email_outbox"))
        report = await audit(integration_engine)
        assert (
            report.total == 4
            and report.changed == 1
            and not report.collision_groups
            and not report.invalid_ids
        )
        assert await snapshot(integration_engine, "registrations") == before  # read-only audit.
        await migrate(integration_engine, command.upgrade, config, "head")
        after = await snapshot(integration_engine, "registrations")
        # Only email changes, neither payloads nor registration/token/ticket identities.
        for old, new in zip(before, after, strict=True):
            assert old[:2] == new[:2] and old[3:] == new[3:]
            assert new[2] == ("user@xn--fa-hia.de" if old[2] == "user@faß.de" else old[2])
        assert await snapshot(integration_engine, "email_outbox") == messages
        await migrate(integration_engine, command.check, config)
        await migrate(integration_engine, command.downgrade, config, PREVIOUS)
        assert await snapshot(integration_engine, "registrations") == after
        assert await snapshot(integration_engine, "email_outbox") == messages
        await migrate(integration_engine, command.upgrade, config, "head")
        assert await snapshot(integration_engine, "registrations") == after
        await migrate(integration_engine, command.check, config)
    finally:
        await cleanup(integration_engine, config)


@pytest.mark.parametrize(
    "addresses",
    [
        ["user@faß.de", "user@xn--fa-hia.de"],
        ["тест@example.test", "safe@faß.de"],
    ],
)
async def test_collision_or_invalid_email_aborts_whole_migration_without_data_loss(
    integration_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, addresses: list[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        await migrate(integration_engine, command.downgrade, config, PREVIOUS)
        identities = await legacy_rows(integration_engine, uuid4(), addresses)
        if addresses[1] == "user@xn--fa-hia.de":
            async with integration_engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE registrations SET status='cancelled', ticket_code=NULL WHERE id=:id"
                    ),
                    {"id": identities[1]},
                )
        before = await snapshot(integration_engine, "registrations")
        report = await audit(integration_engine)
        assert report.collision_groups or report.invalid_ids
        with pytest.raises(RuntimeError, match="preflight failed") as error:
            await migrate(integration_engine, command.upgrade, config, "head")
        affected = report.invalid_ids + [
            identity for group in report.collision_groups for identity in group
        ]
        assert affected and all(str(identity) in str(error.value) for identity in affected)
        assert all(address not in str(error.value) for address in addresses)
        assert await snapshot(integration_engine, "registrations") == before
        async with integration_engine.connect() as connection:
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version")) == PREVIOUS
            )
    finally:
        await cleanup(integration_engine, config)
