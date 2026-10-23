"""Async SMTP adapter. No payloads, recipient addresses or SMTP replies are logged."""

from aiosmtplib import SMTP

from notifications_app.config import Settings
from notifications_app.mime import PreparedEmail


async def send_email(email: PreparedEmail, *, settings: Settings) -> None:
    client = SMTP(
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        local_hostname="notifications.local",  # Avoid socket.getfqdn() in the event loop.
        timeout=settings.sender_timeout,
        use_tls=False,
        start_tls=False,  # Local Mailpit only; no external credentials or API.
    )
    try:
        await client.connect()
        refused, _ = await client.sendmail(email.sender, [email.recipient], email.data)
        if refused:
            raise ValueError("Unexpected partial SMTP acceptance")
        # sendmail returned after DATA 250. QUIT failure must not undo acceptance.
    finally:
        client.close()
