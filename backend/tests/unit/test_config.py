import pytest
from pydantic import ValidationError

from app.config import Settings


def test_organizer_secret_is_not_represented_in_settings(settings: Settings) -> None:
    assert settings.organizer_token.get_secret_value() not in repr(settings)


@pytest.mark.parametrize("secret", ["", "too-short"])
def test_rejects_short_organizer_secret(settings: Settings, secret: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=str(settings.database_url), organizer_token=secret)


@pytest.mark.parametrize("url", ["sqlite:///app.db", "postgresql://user:password@localhost/events"])
def test_requires_postgresql_psycopg(settings: Settings, url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=url, organizer_token=settings.organizer_token)
