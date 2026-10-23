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
def test_requires_asyncpg(url: str, settings: Settings) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url=url, notifications_internal_token=settings.notifications_internal_token
        )


def test_settings_do_not_represent_database_password(settings: Settings) -> None:
    assert "private-password" not in repr(settings)


@pytest.mark.parametrize("token", ["", "x" * 31])
def test_internal_token_must_be_long_enough(settings: Settings, token: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=settings.database_url, notifications_internal_token=token)


def test_internal_token_is_not_represented(settings: Settings) -> None:
    assert settings.notifications_internal_token.get_secret_value() not in repr(settings)
