import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from tests.integration.business_support import Business
from tests.integration.test_migrations import migrate

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_new_migration_preserves_data_and_blocks_loss_of_forwarded_state(
    business: Business,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    event = await business.create()
    await business.join(event.id, "migration@example.test")
    engine = business.engine
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    async with engine.connect() as connection:
        before = (await connection.execute(text("SELECT * FROM email_outbox ORDER BY id"))).all()
    await migrate(engine, command.downgrade, config, "0002_simplify_schema")
    await migrate(engine, command.upgrade, config, "head")
    async with engine.begin() as connection:
        after = (await connection.execute(text("SELECT * FROM email_outbox ORDER BY id"))).all()
        assert before == after
        await connection.execute(
            text(
                "UPDATE email_outbox SET status='forwarded', prepared_at=now() WHERE kind='ticket'"
            )
        )
    with pytest.raises(RuntimeError, match="forwarded jobs"):
        await migrate(engine, command.downgrade, config, "0002_simplify_schema")
    await migrate(engine, command.check, config)
