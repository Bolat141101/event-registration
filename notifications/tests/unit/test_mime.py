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
        "description": "Event café\nBcc: victim@example.test",
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
    assert "Event café" in text and "http://localhost:8080/registration#token=private-token" in text
    assert "Schedule version: 1" in text and "snapshot" in text
    assert ("private-ticket" in text) == (kind != "waitlist")
    if kind == "rescheduled":
        assert "Previous start" in text and "New start" in text
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


@pytest.mark.parametrize(
    "address,expected",
    [
        ("user@faß.de", "user@xn--fa-hia.de"),
        ("user@xn--fa-hia.de", "user@xn--fa-hia.de"),
        (" USER@FAẞ.DE ", "user@xn--fa-hia.de"),
        ("user@fass.de", "user@fass.de"),
        ("Some.One+Tag@EXAMPLE.test", "some.one+tag@example.test"),
    ],
)
def test_mailbox_idna2008_ascii_domain(address: str, expected: str) -> None:
    assert mailbox(address) == expected


def test_legacy_payload_is_not_rewritten_and_wrong_fass_mime_is_rejected() -> None:
    command = message().model_copy(
        update={"payload": message().payload.model_copy(update={"recipient": "user@faß.de"})}
    )
    before = command.model_dump(mode="json")
    data = render(command, "events@example.test", "http://localhost:8080", datetime.now(UTC))
    prepared = load_prepared(command, data)
    assert prepared.recipient == "user@xn--fa-hia.de" and prepared.data == data
    assert b"To: user@xn--fa-hia.de\r\n" in data
    wrong = data.replace(b"user@xn--fa-hia.de", b"user@fass.de")
    with pytest.raises(ValueError, match="identity"):
        load_prepared(command, wrong)
    assert command.model_dump(mode="json") == before


def test_legacy_ascii_case_mime_preserves_headers_and_bytes() -> None:
    command = message()
    data = render(command, "events@example.test", "http://localhost:8080", datetime.now(UTC))
    data = data.replace(b"From: events@example.test", b"From: Events@Example.test")
    data = data.replace(b"To: user@example.test", b"To: USER@EXAMPLE.TEST")
    data = data.replace(
        f"<{command.message_id}@example.test>".encode(),
        f"<{command.message_id}@Example.test>".encode(),
    )
    prepared = load_prepared(command, data)
    assert prepared.data == data and prepared.recipient == "user@example.test"
    assert prepared.sender == "events@example.test"


def test_legacy_prepared_email_remains_byte_identical_after_copy_translation() -> None:
    command = message()
    mail = BytesParser(policy=policy.SMTP).parsebytes(
        render(command, "events@example.test", "http://localhost:8080", datetime.now(UTC))
    )
    mail.replace_header("Subject", "Legacy notification")
    # Deliberately retain non-English legacy content; deployment must not rewrite MIME.
    mail.set_content("Legacy message: \u0411\u0438\u043b\u0435\u0442", charset="utf-8")
    frozen = mail.as_bytes()
    assert load_prepared(command, frozen).data == frozen
