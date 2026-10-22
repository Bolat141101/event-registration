from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

SERVICE_DIR = Path(__file__).resolve().parents[1]


def expected_schema_heads() -> set[str]:
    config = Config(str(SERVICE_DIR / "alembic.ini"))
    return set(ScriptDirectory.from_config(config).get_heads())


async def database_is_ready(engine: AsyncEngine, expected_heads: set[str]) -> bool:
    async with engine.connect() as connection:
        actual_heads = set(
            (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars()
        )
    return actual_heads == expected_heads and bool(expected_heads)
