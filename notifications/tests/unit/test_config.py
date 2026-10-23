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


@pytest.mark.parametrize(
    "changes",
    [
        {"smtp_port": 0},
        {"smtp_port": 65536},
        {"sender_timeout": 0},
        {"sender_max_attempts": 0},
        {"sender_max_attempts": 101},
        {"sender_poll_interval": 0},
        {"sender_backoff_base": 0},
        {"sender_backoff_cap": 0},
        {"smtp_from": "a@example.test\r\nBcc: evil@example.test"},
        {"public_app_url": "http://user:secret@localhost:8080"},
        {"public_app_url": "http://localhost:8080/path"},
    ],
)
def test_sender_configuration_rejects_invalid_values(
    settings: Settings, changes: dict[str, object]
) -> None:
    document = settings.model_dump()
    document.update(changes)
    with pytest.raises(ValidationError):
        Settings.model_validate(document)


def test_invalid_settings_error_does_not_expose_input(settings: Settings) -> None:
    document = settings.model_dump()
    document.update(
        notifications_internal_token="short-private-token",
        smtp_from="private@example.test\r\nBcc: hidden@example.test",
    )
    with pytest.raises(ValidationError) as error:
        Settings.model_validate(document)
    assert "short-private-token" not in str(error.value)
    assert "private@example.test" not in str(error.value)
    assert "hidden@example.test" not in str(error.value)
