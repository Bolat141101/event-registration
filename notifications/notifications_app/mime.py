"""Render once; SMTP retries consume persisted bytes and their frozen envelope."""

from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime, parsedate_to_datetime
from uuid import UUID

from notifications_app.contract import NotificationMessage
from notifications_app.email_addresses import canonical_email


@dataclass(frozen=True)
class PreparedEmail:
    identity: UUID
    data: bytes = field(repr=False)
    sender: str = field(repr=False)
    recipient: str = field(repr=False)


def mailbox(value: str) -> str:
    # Validation excludes display names, header injection and SMTPUTF8.
    return canonical_email(value)


def render(message: NotificationMessage, sender: str, public_url: str, now: datetime) -> bytes:
    body = message.payload
    titles = {
        "ticket": "Билет на мероприятие",
        "waitlist": "Регистрация в листе ожидания",
        "reminder": "Напоминание о мероприятии",
        "rescheduled": "Перенос мероприятия",
    }
    sender = mailbox(sender)
    mail = EmailMessage(policy=policy.SMTP)
    mail["From"] = sender
    mail["To"] = mailbox(body.recipient)
    mail["Date"] = format_datetime(now)
    mail["Message-ID"] = f"<{message.message_id}@{Address(addr_spec=sender).domain}>"
    mail["Subject"] = titles[message.kind]
    lines = [
        titles[message.kind],
        body.description,
        f"Начало (UTC): {body.starts_at.isoformat()}",
        f"Версия расписания: {body.schedule_version}",
        f"Участие: {body.participation_no}",
        f"Состояние на момент подготовки: {body.registration_status}",
    ]
    if message.kind == "rescheduled":
        assert body.old_starts_at is not None and body.new_starts_at is not None
        lines += [
            f"Прежнее начало (UTC): {body.old_starts_at.isoformat()}",
            f"Новое начало (UTC): {body.new_starts_at.isoformat()}",
        ]
    if body.ticket_code is not None:
        lines.append(f"Код билета: {body.ticket_code}")
    if body.manage_path is not None:
        lines.append(f"Управление регистрацией: {public_url.rstrip('/')}{body.manage_path}")
    lines.append(
        "Это снимок регистрации на момент подготовки уведомления. "
        "После отмены, восстановления или переноса данные могли измениться. "
        "Актуальное состояние и действительность билета определяет сервис регистрации."
    )
    mail.set_content("\n\n".join(lines), charset="utf-8", cte="quoted-printable")
    return mail.as_bytes()


def load_prepared(message: NotificationMessage, data: bytes) -> PreparedEmail:
    # The email parser also parses headers lazily in get_all()/__getitem__.
    try:
        mail = BytesParser(policy=policy.SMTP).parsebytes(data)
        if (
            mail.defects
            or any(
                len(mail.get_all(name, [])) != 1
                for name in ("From", "To", "Date", "Message-ID", "Subject")
            )
            or any(mail.get_all(name) for name in ("Cc", "Bcc", "Resent-To", "Resent-Bcc"))
        ):
            raise ValueError("Invalid prepared MIME")
        raw_sender, raw_recipient = str(mail["From"]), str(mail["To"])
        if not raw_sender.isascii() or not raw_recipient.isascii():
            raise ValueError("Non-ASCII prepared MIME envelope")
        sender = mailbox(raw_sender)
        recipient = mailbox(raw_recipient)
        date = parsedate_to_datetime(str(mail["Date"]))
        if (
            recipient != mailbox(message.payload.recipient)
            or str(mail["Message-ID"]).lower()
            != f"<{message.message_id}@{Address(addr_spec=sender).domain}>"
            or date.tzinfo is None
        ):
            raise ValueError("Invalid prepared MIME identity")
        return PreparedEmail(message.message_id, data, sender, recipient)
    except (IndexError, AttributeError, HeaderParseError) as exc:
        raise ValueError("Invalid prepared MIME") from exc
