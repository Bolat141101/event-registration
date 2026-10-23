from datetime import UTC, datetime
from email import policy
from email.errors import HeaderParseError
from email.parser import BytesParser
from unittest.mock import patch
from uuid import uuid4

import pytest

from notifications_app.contract import NotificationMessage
from notifications_app.mime import load_prepared, mailbox, render


def message(kind: str = "ticket") -> NotificationMessage:
    payload = {
        "recipient": "user@example.test",
        "event_id": str(uuid4()),
        "description": "Событие\nBcc: victim@example.test",
        "starts_at": "2030-01-03T12:00:00Z",
        "schedule_version": 1,
        "participation_no": 1,
        "registration_status": "confirmed",
        "ticket_code": "private-ticket",
        "manage_path": "/registration#token=private-token",
    }
    if kind == "waitlist":
        payload.update(registration_status="waitlisted", ticket_code=None)
    if kind == "rescheduled":
        payload.update(old_starts_at="2030-01-02T12:00:00Z", new_starts_at=payload["starts_at"])
    return NotificationMessage.model_validate(
        {
            "schema_version": 1,
            "message_id": str(uuid4()),
            "registration_id": str(uuid4()),
            "kind": kind,
            "payload": payload,
        }
    )


@pytest.mark.parametrize("kind", ["ticket", "waitlist", "reminder", "rescheduled"])
def test_render_all_kinds_and_no_header_injection(kind: str) -> None:
    command = message(kind)
    data = render(
        command, "events@example.test", "http://localhost:8080", datetime(2030, 1, 1, tzinfo=UTC)
    )
    email = load_prepared(command, data)
    parsed = BytesParser(policy=policy.default).parsebytes(data)
    assert email.data == data and email.recipient == "user@example.test"
    assert parsed["Date"] == "Tue, 01 Jan 2030 00:00:00 +0000"
    assert str(parsed["Message-ID"]) == f"<{command.message_id}@example.test>"
    assert parsed["Bcc"] is None and parsed["Subject"]
    text = parsed.get_content()
    assert "Событие" in text and "http://localhost:8080/registration#token=private-token" in text
    assert "Версия расписания: 1" in text and "снимок" in text
    assert ("private-ticket" in text) == (kind != "waitlist")
    if kind == "rescheduled":
        assert "Прежнее начало" in text and "Новое начало" in text
    assert "private-token" not in repr(email) and "user@example.test" not in repr(email)


@pytest.mark.parametrize(
    "value",
    [
        "a@example.test\r\nBcc: x@y.test",
        "a\x00@example.test",
        "a",
        "a@",
        "a@example.test,b@example.test",
    ],
)
def test_reject_unsafe_mailboxes(value: str) -> None:
    with pytest.raises(ValueError):
        mailbox(value)


def test_idn_domain_without_smtputf8() -> None:
    assert mailbox("user@пример.рф") == "user@xn--e1afmkfd.xn--p1ai"


def test_reject_mime_with_wrong_identity_or_recipient() -> None:
    command = message()
    data = render(command, "events@example.test", "http://localhost:8080", datetime.now(UTC))
    for changed in (
        data.replace(b"user@example.test", b"evil@example.test"),
        data.replace(str(command.message_id).encode(), str(uuid4()).encode()),
        b"Date: bad\r\n\r\nbad",
    ):
        with pytest.raises(ValueError):
            load_prepared(command, changed)


def damaged_mime(command: NotificationMessage, header: str, value: str) -> bytes:
    data = render(
        command, "events@example.test", "http://localhost:8080", datetime(2030, 1, 1, tzinfo=UTC)
    )
    original = f"{header}: {'events' if header == 'From' else 'user'}@example.test\r\n".encode()
    assert original in data
    return data.replace(original, f"{header}: {value}\r\n".encode(), 1)


@pytest.mark.parametrize("header", ["From", "To"])
@pytest.mark.parametrize("value", ['"', "a@["])
def test_damaged_address_header_raises_value_error(header: str, value: str) -> None:
    command = message()
    data = damaged_mime(command, header, value)
    with pytest.raises(ValueError):
        load_prepared(command, data)


@pytest.mark.parametrize("error", [IndexError, AttributeError, HeaderParseError])
def test_header_parser_errors_are_normalized(error: type[Exception]) -> None:
    command = message()
    data = render(command, "events@example.test", "http://localhost:8080", datetime.now(UTC))
    with (
        patch(
            "notifications_app.mime.BytesParser.parsebytes",
            side_effect=error("private-token user@example.test"),
        ),
        pytest.raises(ValueError, match="^Invalid prepared MIME$") as caught,
    ):
        load_prepared(command, data)
    assert isinstance(caught.value.__cause__, error)
