import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_organizer_secret_is_not_represented_in_settings(settings: Settings) -> None:
    assert settings.organizer_token.get_secret_value() not in repr(settings)


@pytest.mark.parametrize("secret", ["", "too-short"])
def test_rejects_short_organizer_secret(settings: Settings, secret: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=str(settings.database_url), organizer_token=secret)


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///app.db",
        "postgresql://user:password@localhost/events",
        "postgresql+psycopg://user:password@localhost/events",
    ],
)
def test_requires_postgresql_asyncpg(settings: Settings, url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=url, organizer_token=settings.organizer_token)


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"database_url": "postgresql://user:fake-db-password@localhost/test"}, "database_url"),
        ({"database_url": "not-a-url-fake-db-password"}, "database_url"),
        ({"organizer_token": "fake-short-token"}, "organizer_token"),
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
    document.update(
        organizer_token="fake-repr-organizer-token-123456789",
        notifications_url="http://fake-user:fake-url-password@localhost:8000",
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
    assert "organizer_token=" not in diagnostic
    assert "notifications_url=" not in diagnostic
    assert "relay_timeout=5" in diagnostic


@pytest.mark.parametrize(
    "arguments",
    [
        ["uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "0"],
        ["app.worker"],
        ["app.email_audit"],
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
    assert "organizer_token" in diagnostic
    assert "at least 32" in diagnostic
    for secret in (
        "fake-user",
        "fake-startup-password",
        "fake-organizer-token",
        "fake-internal-token",
    ):
        assert secret not in diagnostic
    assert "input_value=" not in diagnostic
