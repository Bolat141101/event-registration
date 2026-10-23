import os
import subprocess
import sys
from pathlib import Path

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


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"database_url": "postgresql://user:fake-db-password@localhost/test"}, "database_url"),
        ({"database_url": "not-a-url-fake-db-password"}, "database_url"),
        ({"notifications_internal_token": "fake-short-token"}, "notifications_internal_token"),
    ],
)
def test_configuration_errors_hide_inputs_but_keep_diagnostics(
    settings: Settings, changes: dict[str, object], field: str
) -> None:
    document = settings.model_dump()
    document.update(changes)
    with pytest.raises(ValidationError) as error:
        Settings.model_validate(document)
    diagnostic = str(error.value) + repr(error.value)
    assert field in diagnostic
    assert "type=" in diagnostic
    assert "fake-db-password" not in diagnostic
    assert "fake-short-token" not in diagnostic
    assert "input_value=" not in diagnostic
    assert "input_type=" not in diagnostic


def test_sensitive_fields_are_excluded_from_settings_repr(settings: Settings) -> None:
    document = settings.model_dump()
    document.update(
        database_url="postgresql+asyncpg://fake-user:fake-repr-password@localhost/test",
        notifications_internal_token="fake-repr-internal-token-123456789",
    )
    configured = Settings.model_validate(document)
    diagnostic = repr(configured) + str(configured)
    for secret in (
        "fake-user",
        "fake-repr-password",
        "fake-repr-internal-token",
        "fake-repr-organizer-token",
        "fake-url-password",
    ):
        assert secret not in diagnostic
    assert configured.notifications_internal_token is not None
    assert (
        configured.notifications_internal_token.get_secret_value()
        == document["notifications_internal_token"]
    )
    assert "database_url=" not in diagnostic
    assert "notifications_internal_token=" not in diagnostic
    assert "smtp_from=" not in diagnostic
    assert "smtp_port=1025" in diagnostic


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "uvicorn",
            "notifications_app.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
        ],
        ["notifications_app.worker"],
        [
            "notifications_app.retry",
            "00000000-0000-0000-0000-000000000001",
            "--acknowledge-duplicate-risk",
        ],
        ["alembic", "upgrade", "head"],
    ],
    ids=["api", "worker", "operator-cli", "alembic"],
)
def test_real_startup_diagnostics_do_not_leak_configuration(
    arguments: list[str],
) -> None:
    # Wrong driver and short tokens fail before any DB/HTTP/SMTP connection is made.
    environment = os.environ | {
        "DATABASE_URL": "postgresql://fake-user:fake-startup-password@127.0.0.1:1/test",
        "ORGANIZER_TOKEN": "fake-organizer-token",
        "NOTIFICATIONS_INTERNAL_TOKEN": "fake-internal-token",
    }
    process = subprocess.run(
        [sys.executable, "-m", *arguments],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert process.returncode != 0
    diagnostic = process.stdout + process.stderr
    assert "ValidationError" in diagnostic
    assert "database_url" in diagnostic
    assert "DATABASE_URL must use postgresql+asyncpg" in diagnostic
    assert "notifications_internal_token" in diagnostic
    assert "at least 32" in diagnostic
    for secret in (
        "fake-user",
        "fake-startup-password",
        "fake-organizer-token",
        "fake-internal-token",
    ):
        assert secret not in diagnostic
    assert "input_value=" not in diagnostic
