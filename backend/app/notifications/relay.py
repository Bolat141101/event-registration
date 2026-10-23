"""One sequential relay. Short event-locked DB phases around transaction-free HTTP."""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clock import Clock, as_utc, utc_now
from app.config import Settings
from app.db.models import (
    EmailOutbox,
    Event,
    NotificationKind,
    OutboxStatus,
    Registration,
    RegistrationStatus,
)
from app.notifications.contract import NotificationAccepted, NotificationMessage
from app.notifications.outbox import context


class Relay:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        client: httpx.AsyncClient,
        settings: Settings,
        clock: Clock = utc_now,
    ) -> None:
        if settings.notifications_internal_token is None:
            raise ValueError("NOTIFICATIONS_INTERNAL_TOKEN is required for the relay")
        self.sessions = sessions
        self.client = client
        self.settings = settings
        self.clock = clock
        # Scheduling hints only, never ownership or delivery state. A finite due
        # sweep and event cursor keep a busy prefix from monopolizing every poll.
        self._sweep_cutoff: datetime | None = None
        self._event_cursor: UUID | None = None

    async def _candidates(self) -> list[tuple[UUID, UUID]]:
        for _ in range(2):  # At most one wrap, including an empty queue.
            if self._sweep_cutoff is None:
                self._sweep_cutoff = as_utc(self.clock())
            heads = (
                select(Registration.event_id, EmailOutbox.id)
                .join(EmailOutbox, EmailOutbox.registration_id == Registration.id)
                .where(
                    EmailOutbox.status == OutboxStatus.PENDING,
                    EmailOutbox.available_at <= self._sweep_cutoff,
                )
                .distinct(Registration.event_id)
                .order_by(Registration.event_id, EmailOutbox.available_at, EmailOutbox.id)
                .subquery()
            )
            query = select(heads.c.event_id, heads.c.id).order_by(heads.c.event_id)
            if self._event_cursor is not None:
                query = query.where(heads.c.event_id > self._event_cursor)
            async with self.sessions() as session:
                rows = (
                    await session.execute(query.limit(self.settings.relay_candidate_limit))
                ).all()
            if rows:
                return [(row.event_id, row.id) for row in rows]
            # Start a fresh sweep. Jobs becoming due during a sweep join the next
            # one, so a stream of new jobs cannot extend the current due horizon.
            self._event_cursor = None
            self._sweep_cutoff = None
        return []

    def backoff(self, attempts: int) -> float:
        return float(
            min(
                self.settings.relay_backoff_cap,
                self.settings.relay_backoff_base * 2 ** (attempts - 1),
            )
        )

    async def prepare(self, identity: UUID) -> NotificationMessage | None:
        async with self.sessions() as session, session.begin():
            event_id = await session.scalar(
                select(Registration.event_id)
                .join(EmailOutbox, EmailOutbox.registration_id == Registration.id)
                .where(EmailOutbox.id == identity)
            )
            if event_id is None:
                return None
            event = await session.scalar(
                select(Event).where(Event.id == event_id).with_for_update(nowait=True)
            )
            if event is None:
                return None
            # Read all state AFTER the event lock in a fresh READ COMMITTED statement.
            message = await session.get(EmailOutbox, identity)
            if message is None or message.status != OutboxStatus.PENDING:
                return None
            now = as_utc(self.clock())
            if message.available_at > now:
                return None
            entry = await session.get(Registration, message.registration_id)
            assert entry is not None
            if message.prepared_at is None:
                if (
                    entry.status == RegistrationStatus.CANCELLED
                    or message.payload.get("participation_no") != entry.participation_no
                    or (message.kind == NotificationKind.REMINDER and now >= event.starts_at)
                ):
                    message.status = OutboxStatus.CANCELLED
                    return None
                if message.kind in (
                    NotificationKind.TICKET,
                    NotificationKind.WAITLIST,
                    NotificationKind.REMINDER,
                ):
                    payload = context(entry, event)
                    if "manage_path" in message.payload:
                        payload["manage_path"] = message.payload["manage_path"]
                    if message.kind == NotificationKind.WAITLIST:
                        payload["ticket_code"] = None
                    message.payload = payload
                if (
                    message.kind == NotificationKind.REMINDER
                    and (deadline := event.starts_at - timedelta(hours=24)) > now
                ):
                    message.available_at = deadline
                    return None
            # Prepared commands may already be accepted after a lost response. Even
            # after cancel/resume/reschedule/expiry, retry EXACTLY that command. We
            # have read the current generation/version/time under the same event lock.
            try:
                if "schema_version" in message.payload:
                    command = NotificationMessage.model_validate(message.payload)
                    if (
                        command.message_id != message.id
                        or command.registration_id != entry.id
                        or command.kind != message.kind.value
                    ):
                        raise ValueError("Stored command identity mismatch")
                else:
                    # v0 infrastructure could contain a flat prepared context. Treat
                    # it as v1 without modifying its persisted payload on retries.
                    command = NotificationMessage.model_validate(
                        {
                            "schema_version": 1,
                            "message_id": message.id,
                            "registration_id": entry.id,
                            "kind": message.kind.value,
                            "payload": message.payload,
                        }
                    )
                if (
                    command.payload.schedule_version > event.schedule_version
                    or command.payload.participation_no > entry.participation_no
                    or command.payload.event_id != event.id
                ):
                    raise ValueError("Stored command has invalid versions or event identity")
            except ValueError:
                message.status = OutboxStatus.FAILED
                message.last_error = "Invalid stored notification contract"
                return None
            if message.attempts >= self.settings.relay_max_attempts:
                message.status = OutboxStatus.FAILED
                message.last_error = "Relay attempt limit reached; explicit retry required"
                return None
            if message.prepared_at is None:
                message.payload = command.model_dump(mode="json")
                message.prepared_at = now
            message.attempts += 1
            # Persist retry timing BEFORE HTTP, including process death before ack.
            message.available_at = now + timedelta(seconds=self.backoff(message.attempts))
        return command

    async def finish(
        self, identity: UUID, accepted: bool, error: str | None, permanent: bool
    ) -> None:
        async with self.sessions() as session, session.begin():
            message = await session.get(EmailOutbox, identity)
            if message is None or message.status != OutboxStatus.PENDING:
                return
            if accepted:
                message.status = OutboxStatus.FORWARDED
                message.last_error = None
            else:
                message.last_error = error
                message.available_at = as_utc(self.clock()) + timedelta(
                    seconds=self.backoff(message.attempts)
                )
                if permanent or message.attempts >= self.settings.relay_max_attempts:
                    message.status = OutboxStatus.FAILED

    async def run_once(self) -> bool:
        for event_id, identity in await self._candidates():
            self._event_cursor = event_id
            try:
                command = await self.prepare(identity)
            except DBAPIError as exc:
                if getattr(exc.orig, "sqlstate", None) != "55P03":
                    raise
                # NOWAIT and lock_timeout both use 55P03. prepare's context has
                # already rolled back and released all locks before continuing.
                # Do not touch payload, attempts or retry time for a busy event.
                continue
            if command is None:
                return True  # Cancelled, deferred or concurrently changed job.
            await self._deliver(command)
            return True  # Preserve one HTTP attempt per run_once.
        # Every candidate was locked (or the queue is empty). The worker sleeps
        # before the next bounded page; no active loop or permanent exclusion.
        return False

    async def _deliver(self, command: NotificationMessage) -> None:
        accepted, permanent, error = False, False, None
        token = self.settings.notifications_internal_token
        assert token is not None
        try:
            async with asyncio.timeout(self.settings.relay_timeout):
                response = await self.client.post(
                    f"{str(self.settings.notifications_url).rstrip('/')}/internal/v1/notifications",
                    json=command.model_dump(mode="json"),
                    headers={"Authorization": f"Bearer {token.get_secret_value()}"},
                    timeout=httpx.Timeout(self.settings.relay_timeout),
                    follow_redirects=False,
                )
            if response.status_code == 202:
                try:
                    ack = NotificationAccepted.model_validate_json(response.content)
                    accepted = ack.message_id == command.message_id
                except ValidationError:
                    accepted = False
                if not accepted:
                    error = "Invalid acceptance acknowledgement"
            else:
                error = f"Notifications HTTP {response.status_code}"
                permanent = response.status_code not in (408, 429) and response.status_code < 500
        except (httpx.TransportError, TimeoutError) as exc:
            error = f"Notifications transport error: {type(exc).__name__}"
        # No response bodies, headers, payloads or exception text go into diagnostics.
        await self.finish(command.message_id, accepted, error, permanent)
