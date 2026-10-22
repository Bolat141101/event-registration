import pytest
from pydantic import ValidationError

from notifications_app.config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///app.db",
        "postgresql://user:password@localhost/test",
        "postgresql+psycopg://user:password@localhost/test",
    ],
)
def test_requires_asyncpg(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=url)


def test_settings_do_not_represent_database_password(settings: Settings) -> None:
    assert "private-password" not in repr(settings)
