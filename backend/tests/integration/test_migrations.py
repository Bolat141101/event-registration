import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from app.db.health import database_is_ready, expected_schema_heads

pytestmark = pytest.mark.integration


def test_migration_round_trip(integration_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
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
