"""One sequential sender: durable prepare, transaction-free SMTP, durable outcome."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID

from aiosmtplib.errors import SMTPException, SMTPRecipientsRefused, SMTPResponseException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notifications_app.clock import Clock, utc_now
from notifications_app.config import Settings
from notifications_app.contract import NotificationMessage
from notifications_app.mime import PreparedEmail, load_prepared, render
from notifications_app.models import JobStatus, NotificationJob

type Delivery = Callable[[PreparedEmail], Awaitable[None]]


class Sender:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        settings: Settings,
        deliver: Delivery,
        clock: Clock = utc_now,
    ) -> None:
        self.sessions = sessions
        self.settings = settings
        self.deliver = deliver
        self.clock = clock

    def backoff(self, attempts: int) -> float:
        return float(
            min(
                self.settings.sender_backoff_cap,
                self.settings.sender_backoff_base * 2 ** (attempts - 1),
            )
        )

    async def prepare(self, identity: UUID) -> PreparedEmail | None:
        async with self.sessions() as session, session.begin():
            job = await session.get(NotificationJob, identity, with_for_update=True)
            if job is None or job.status != JobStatus.PENDING or job.available_at > self.clock():
                return None
            if job.attempts >= self.settings.sender_max_attempts:
                job.status = JobStatus.FAILED
                job.last_error = "SMTP attempt limit reached; explicit retry required"
                return None
            try:
                message = NotificationMessage.model_validate(job.payload)
                if message.message_id != job.id:
                    raise ValueError("Stored message identity mismatch")
                if job.mime is None:
                    job.mime = render(
                        message,
                        self.settings.smtp_from,
                        str(self.settings.public_app_url),
                        self.clock(),
                    )
                prepared = load_prepared(message, job.mime)
            except (ValueError, TypeError, OverflowError):
                job.status = JobStatus.FAILED
                job.last_error = "Invalid stored payload or MIME"
                return None
            job.attempts += 1
            job.available_at = self.clock() + timedelta(seconds=self.backoff(job.attempts))
        return prepared

    async def finish(self, identity: UUID, error: str | None, permanent: bool) -> None:
        async with self.sessions() as session, session.begin():
            job = await session.get(NotificationJob, identity, with_for_update=True)
            if job is None or job.status != JobStatus.PENDING:
                return
            if error is None:
                job.status = JobStatus.SENT
                job.last_error = None
            else:
                job.last_error = error
                job.available_at = self.clock() + timedelta(seconds=self.backoff(job.attempts))
                if permanent or job.attempts >= self.settings.sender_max_attempts:
                    job.status = JobStatus.FAILED

    async def run_once(self) -> bool:
        async with self.sessions() as session:
            identity = await session.scalar(
                select(NotificationJob.id)
                .where(
                    NotificationJob.status == JobStatus.PENDING,
                    NotificationJob.available_at <= self.clock(),
                )
                .order_by(NotificationJob.available_at, NotificationJob.id)
                .limit(1)
            )
        if identity is None:
            return False
        prepared = await self.prepare(identity)
        if prepared is None:
            return True
        error, permanent = None, False
        try:
            async with asyncio.timeout(self.settings.sender_timeout):
                await self.deliver(prepared)
        except SMTPRecipientsRefused as exc:
            permanent = bool(exc.recipients) and all(
                500 <= item.code < 600 for item in exc.recipients
            )
            error = "SMTP recipients rejected"  # Never persist exception/response text.
        except SMTPResponseException as exc:
            permanent = 500 <= exc.code < 600
            error = f"SMTP response {exc.code}"
        except (SMTPException, OSError, TimeoutError) as exc:
            error = f"SMTP transport error: {type(exc).__name__}"
        except ValueError:
            error, permanent = "Invalid SMTP envelope", True
        await self.finish(identity, error, permanent)
        return True
