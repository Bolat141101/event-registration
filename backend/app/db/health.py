from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

BACKEND_DIR = Path(__file__).resolve().parents[2]


def expected_schema_heads() -> set[str]:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    return set(ScriptDirectory.from_config(config).get_heads())


def database_is_ready(engine: Engine, expected_heads: set[str]) -> bool:
    with engine.connect() as connection:
        actual_heads = set(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
        )
    return actual_heads == expected_heads and bool(expected_heads)
