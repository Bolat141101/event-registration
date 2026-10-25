import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

import pytest
from aiosmtplib.errors import SMTPDataError, SMTPRecipientRefused, SMTPRecipientsRefused
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from notifications_app.config import Settings
from notifications_app.contract import NotificationMessage
from notifications_app.inbox import MessageConflict, accept_message
from notifications_app.mime import PreparedEmail, render
from notifications_app.models import JobStatus, NotificationJob
from notifications_app.retry import retry_failed
from notifications_app.sender import Sender
from tests.unit.test_mime import damaged_mime, message

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2030, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
async def command(integration_engine: AsyncEngine) -> AsyncIterator[NotificationMessage]:
    command = message()
    async with integration_engine.begin() as connection:
        await connection.execute(
            NotificationJob.__table__.insert().values(
                id=command.message_id,
                payload=command.model_dump(mode="json"),
                available_at=datetime(2030, 1, 1, tzinfo=UTC),
            )
        )
    try:
        yield command
    finally:
        async with integration_engine.begin() as connection:
            await connection.execute(
                delete(NotificationJob).where(NotificationJob.id == command.message_id)
            )


@pytest.fixture
def sender_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "sender_max_attempts": 3,
            "sender_timeout": 0.1,
            "sender_backoff_base": 1,
            "sender_backoff_cap": 2,
        }
    )


async def stored(engine: AsyncEngine, identity: UUID) -> NotificationJob:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        job = await session.get(NotificationJob, identity)
        assert job is not None
        return job


async def test_persist_before_network_no_open_transaction_and_no_early_or_second_send(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    delivered = []

    async def deliver(email: PreparedEmail) -> None:
        job = await stored(integration_engine, command.message_id)
        assert job.mime == email.data and job.attempts == 1 and job.status == JobStatus.PENDING
        async with integration_engine.begin() as connection:
            await connection.execute(
                select(NotificationJob.id)
                .where(NotificationJob.id == job.id)
                .with_for_update(nowait=True)
            )
            assert not await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                    "AND state='idle in transaction' AND pid<>pg_backend_pid()"
                )
            )
        delivered.append(email)

    sender = Sender(sessions, sender_settings, deliver, clock)
    clock.now -= timedelta(seconds=1)
    assert not await sender.run_once()
    clock.now += timedelta(seconds=1)
    assert await sender.run_once()
    assert (await stored(integration_engine, command.message_id)).status == JobStatus.SENT
    assert len(delivered) == 1 and not await sender.run_once()


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionRefusedError("private-token user@example.test"),
        SMTPDataError(451, "private-token user@example.test"),
        TimeoutError("private-token"),
    ],
)
async def test_failure_restart_and_retry_preserve_mime_and_envelope(
    integration_engine: AsyncEngine,
    command: NotificationMessage,
    sender_settings: Settings,
    failure: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    sent = []

    async def fail(email: PreparedEmail) -> None:
        sent.append(email)
        raise failure

    sender = Sender(sessions, sender_settings, fail, clock)
    assert await sender.run_once()
    before = await stored(integration_engine, command.message_id)
    assert before.status == JobStatus.PENDING and before.attempts == 1 and before.mime
    assert before.available_at == clock.now + timedelta(seconds=1)
    assert (
        before.last_error
        and "private-token" not in before.last_error
        and "@" not in before.last_error
    )
    assert not await sender.run_once()
    await integration_engine.dispose()
    clock.now += timedelta(seconds=1)

    async def succeed(email: PreparedEmail) -> None:
        sent.append(email)

    changed = sender_settings.model_copy(update={"smtp_from": "new@example.test"})
    sender = Sender(sessions, changed, succeed, clock)
    assert await sender.run_once()
    after = await stored(integration_engine, command.message_id)
    assert after.mime == before.mime and after.payload == before.payload
    assert after.status == JobStatus.SENT and after.attempts == 2 and after.last_error is None
    assert sent[0] == sent[1] and "private-token" not in caplog.text
    assert "user@example.test" not in caplog.text


async def test_timeout_does_not_block_event_loop(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    ticks = []

    async def slow(_: PreparedEmail) -> None:
        for _ in range(100):
            await asyncio.sleep(0.01)
            ticks.append(1)

    sender = Sender(async_sessionmaker(integration_engine), sender_settings, slow, Clock())
    assert await asyncio.wait_for(sender.run_once(), timeout=1)
    row = await stored(integration_engine, command.message_id)
    assert (
        ticks
        and row.status == JobStatus.PENDING
        and row.last_error == "SMTP transport error: TimeoutError"
    )


async def test_budget_exhaustion_http_replay_does_not_revive_and_manual_retry_keeps_bytes(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)

    async def fail(_: PreparedEmail) -> None:
        raise ConnectionRefusedError()

    sender = Sender(sessions, sender_settings, fail, clock)
    for attempt in range(1, 4):
        assert await sender.run_once()
        row = await stored(integration_engine, command.message_id)
        assert row.attempts == attempt
        clock.now = row.available_at
    assert row.status == JobStatus.FAILED and not await sender.run_once()
    original = (row.payload, row.mime, row.last_error)
    async with sessions() as session:
        await accept_message(session, command)
    row = await stored(integration_engine, command.message_id)
    assert row.status == JobStatus.FAILED and row.attempts == 3
    assert await retry_failed(sessions, command.message_id, clock)
    assert not await retry_failed(sessions, command.message_id, clock)

    async def succeed(_: PreparedEmail) -> None:
        pass

    assert await Sender(sessions, sender_settings, succeed, clock).run_once()
    row = await stored(integration_engine, command.message_id)
    assert row.status == JobStatus.SENT and row.attempts == 1
    assert (row.payload, row.mime) == original[:2]
    assert not await retry_failed(sessions, command.message_id, clock)


@pytest.mark.parametrize(
    "failure",
    [
        SMTPDataError(550, "secret"),
        SMTPRecipientsRefused([SMTPRecipientRefused(550, "secret", "user@example.test")]),
    ],
)
async def test_permanent_smtp_error_is_failed_without_automatic_retry(
    integration_engine: AsyncEngine,
    command: NotificationMessage,
    sender_settings: Settings,
    failure: Exception,
) -> None:
    async def deliver(_: PreparedEmail) -> None:
        raise failure

    sender = Sender(async_sessionmaker(integration_engine), sender_settings, deliver, Clock())
    assert await sender.run_once()
    row = await stored(integration_engine, command.message_id)
    assert row.status == JobStatus.FAILED and row.attempts == 1 and row.mime
    assert not await sender.run_once()


async def test_crash_after_prepare_or_after_smtp_accept_resumes_same_mime(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    sent = []

    async def deliver(email: PreparedEmail) -> None:
        sent.append(email)

    sender = Sender(sessions, sender_settings, deliver, clock)
    prepared = await sender.prepare(command.message_id)
    assert prepared is not None and not sent  # Death before SMTP.
    clock.now += timedelta(seconds=1)
    sender = Sender(sessions, sender_settings, deliver, clock)
    with (
        patch.object(sender, "finish", side_effect=RuntimeError("death after accept")),
        pytest.raises(RuntimeError),
    ):
        await sender.run_once()
    assert len(sent) == 1
    clock.now += timedelta(seconds=2)
    sender = Sender(sessions, sender_settings, deliver, clock)
    assert await sender.run_once()
    assert sent == [prepared, prepared]  # SMTP can duplicate; never promise exactly-once.
    assert (await stored(integration_engine, command.message_id)).status == JobStatus.SENT


async def test_last_attempt_crash_requires_explicit_retry(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)

    async def deliver(_: PreparedEmail) -> None:
        pytest.fail("Last reserved attempt must not send again after process death")

    sender = Sender(
        sessions, sender_settings.model_copy(update={"sender_max_attempts": 1}), deliver, clock
    )
    assert await sender.prepare(command.message_id)
    clock.now += timedelta(seconds=1)
    assert await sender.run_once()
    assert (await stored(integration_engine, command.message_id)).status == JobStatus.FAILED


@pytest.mark.parametrize("prepared", [False, True])
async def test_old_or_conflicting_http_message_cannot_replace_or_revive_job(
    integration_engine: AsyncEngine,
    command: NotificationMessage,
    sender_settings: Settings,
    prepared: bool,
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)

    async def fail(_: PreparedEmail) -> None:
        raise SMTPDataError(550, "rejected")

    sender = Sender(sessions, sender_settings, fail, clock)
    if prepared:
        assert await sender.prepare(command.message_id)
    async with sessions() as session, session.begin():
        job = await session.get(NotificationJob, command.message_id)
        assert job is not None
        job.status = JobStatus.FAILED
    before = await stored(integration_engine, command.message_id)
    async with sessions() as session:
        await accept_message(session, command)
    changed = deepcopy(command.model_dump(mode="json"))
    changed["payload"]["schedule_version"] += 1
    async with sessions() as session:
        with pytest.raises(MessageConflict):
            await accept_message(session, NotificationMessage.model_validate(changed))
    after = await stored(integration_engine, command.message_id)
    assert (after.status, after.payload, after.mime, after.attempts) == (
        before.status,
        before.payload,
        before.mime,
        before.attempts,
    )
    assert not await sender.run_once()


async def test_invalid_legacy_payload_is_preserved_failed_not_sent_or_manually_reactivated(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        job = await session.get(NotificationJob, command.message_id)
        assert job is not None
        job.payload = {"legacy": True}

    async def deliver(_: PreparedEmail) -> None:
        pytest.fail("Invalid legacy data must not be sent")

    assert await Sender(sessions, sender_settings, deliver, Clock()).run_once()
    row = await stored(integration_engine, command.message_id)
    assert row.status == JobStatus.FAILED and row.payload == {"legacy": True} and row.attempts == 0
    with pytest.raises(ValueError):
        await retry_failed(sessions, command.message_id, Clock())


async def test_retry_cli_requires_explicit_risk_ack_and_keeps_frozen_data(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    import os
    import sys

    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)

    async def deliver(_: PreparedEmail) -> None:
        raise SMTPDataError(550, "permanent failure")

    assert await Sender(sessions, sender_settings, deliver, Clock()).run_once()
    before = await stored(integration_engine, command.message_id)
    assert before.status == JobStatus.FAILED and before.mime

    async def run_cli(*arguments: str) -> tuple[int | None, bytes]:
        environment = {
            **os.environ,
            "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "notifications_app.retry",
            str(command.message_id),
            *arguments,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        return process.returncode, stdout + stderr

    code, output = await run_cli()
    assert code == 2
    assert (await stored(integration_engine, command.message_id)).status == JobStatus.FAILED
    code, output = await run_cli("--acknowledge-duplicate-risk")
    assert code == 0
    row = await stored(integration_engine, command.message_id)
    assert row.status == JobStatus.PENDING and row.attempts == 0
    assert (row.mime, row.payload, row.last_error) == (
        before.mime,
        before.payload,
        before.last_error,
    )
    code, output = await run_cli("--acknowledge-duplicate-risk")
    assert code != 0 and "private-token" not in output.decode()
    assert "user@example.test" not in output.decode()


@pytest.mark.parametrize("header", ["From", "To"])
@pytest.mark.parametrize("value", ['"', "a@["])
async def test_damaged_mime_fails_without_smtp_and_next_job_is_sent(
    integration_engine: AsyncEngine,
    command: NotificationMessage,
    sender_settings: Settings,
    header: str,
    value: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    data = damaged_mime(command, header, value)
    good = message()
    async with sessions() as session, session.begin():
        bad = await session.get(NotificationJob, command.message_id)
        assert bad is not None
        bad.mime = data
        bad.available_at = clock.now - timedelta(seconds=2)
        session.add(
            NotificationJob(
                id=good.message_id,
                payload=good.model_dump(mode="json"),
                available_at=clock.now - timedelta(seconds=1),
            )
        )
    delivered: list[PreparedEmail] = []

    async def deliver(email: PreparedEmail) -> None:
        delivered.append(email)

    sender = Sender(sessions, sender_settings, deliver, clock)
    before = await stored(integration_engine, command.message_id)
    try:
        with patch("notifications_app.sender.render", wraps=render) as renderer:
            assert await sender.run_once()
            renderer.assert_not_called()
            assert not delivered
            bad = await stored(integration_engine, command.message_id)
            assert bad.status == JobStatus.FAILED
            assert bad.last_error == "Invalid stored payload or MIME"
            assert (bad.payload, bad.mime, bad.attempts, bad.available_at) == (
                before.payload,
                before.mime,
                before.attempts,
                before.available_at,
            )
            assert await sender.run_once()
            renderer.assert_called_once()
            assert renderer.call_args.args[0].message_id == good.message_id
        assert len(delivered) == 1 and delivered[0].identity == good.message_id
        sent = await stored(integration_engine, good.message_id)
        assert sent.status == JobStatus.SENT and sent.mime == delivered[0].data
        assert (await stored(integration_engine, command.message_id)).status == JobStatus.FAILED
        assert not await sender.run_once()
        assert "private-token" not in caplog.text and "user@example.test" not in caplog.text
    finally:
        async with sessions() as session, session.begin():
            await session.execute(
                delete(NotificationJob).where(NotificationJob.id == good.message_id)
            )


async def test_unsafe_legacy_idn_mime_is_failed_without_rewrite_or_queue_blocking(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    legacy = command.model_copy(
        update={"payload": command.payload.model_copy(update={"recipient": "user@faß.de"})}
    )
    frozen = render(legacy, "events@example.test", "http://localhost:8080", clock())
    frozen = frozen.replace(b"user@xn--fa-hia.de", b"user@fass.de")
    good = message()
    async with sessions() as session, session.begin():
        row = await session.get(NotificationJob, command.message_id)
        assert row is not None
        row.payload = legacy.model_dump(mode="json")
        row.mime = frozen
        row.attempts = 1
        row.available_at = clock.now - timedelta(seconds=2)
        session.add(
            NotificationJob(
                id=good.message_id,
                payload=good.model_dump(mode="json"),
                available_at=clock.now - timedelta(seconds=1),
            )
        )
    sent: list[PreparedEmail] = []

    async def deliver(email: PreparedEmail) -> None:
        sent.append(email)

    sender = Sender(sessions, sender_settings, deliver, clock)
    before = await stored(integration_engine, command.message_id)
    try:
        assert await sender.run_once()
        assert not sent
        row = await stored(integration_engine, command.message_id)
        assert row.status == JobStatus.FAILED and row.last_error == "Invalid stored payload or MIME"
        assert (row.mime, row.payload, row.attempts, row.available_at) == (
            before.mime,
            before.payload,
            before.attempts,
            before.available_at,
        )
        assert await sender.run_once()
        assert len(sent) == 1 and sent[0].identity == good.message_id
        assert (await stored(integration_engine, good.message_id)).status == JobStatus.SENT
        with pytest.raises(ValueError):
            await retry_failed(sessions, command.message_id, clock)
        assert (await stored(integration_engine, command.message_id)).mime == frozen
    finally:
        async with sessions() as session, session.begin():
            await session.execute(
                delete(NotificationJob).where(NotificationJob.id == good.message_id)
            )


@pytest.mark.parametrize("has_mime", [False, True])
async def test_legacy_unicode_payload_is_accepted_without_rewrite_and_smtp_uses_ascii(
    integration_engine: AsyncEngine,
    command: NotificationMessage,
    sender_settings: Settings,
    has_mime: bool,
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    legacy = command.model_copy(
        update={"payload": command.payload.model_copy(update={"recipient": "user@faß.de"})}
    )
    frozen = (
        render(legacy, "events@example.test", "http://localhost:8080", clock())
        if has_mime
        else None
    )
    async with sessions() as session, session.begin():
        row = await session.get(NotificationJob, command.message_id)
        assert row is not None
        row.payload = legacy.model_dump(mode="json")
        row.mime = frozen
    delivered: list[PreparedEmail] = []

    async def deliver(email: PreparedEmail) -> None:
        delivered.append(email)

    assert await Sender(sessions, sender_settings, deliver, clock).run_once()
    assert len(delivered) == 1 and delivered[0].recipient == "user@xn--fa-hia.de"
    row = await stored(integration_engine, command.message_id)
    assert row.status == JobStatus.SENT and row.payload == legacy.model_dump(mode="json")
    if has_mime:
        assert row.mime == frozen


async def test_two_senders_cannot_overlap_after_retry_becomes_due(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    entered, release = asyncio.Event(), asyncio.Event()
    delivered: list[bytes] = []

    async def deliver(email: PreparedEmail) -> None:
        delivered.append(email.data)
        entered.set()
        await release.wait()

    settings = sender_settings.model_copy(update={"sender_timeout": 5.0})
    first = asyncio.create_task(Sender(sessions, settings, deliver, clock).run_once())
    await asyncio.wait_for(entered.wait(), 3)
    clock.now += timedelta(seconds=10)  # First SMTP still running, durable retry already due.
    try:
        assert not await Sender(sessions, settings, deliver, clock).run_once()
        # A DIFFERENT interpreter also observes PostgreSQL ownership, not a Python mutex.
        import os
        import sys

        code = """
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from notifications_app.singleton import singleton
async def main():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with singleton(async_sessionmaker(engine)) as acquired:
        print(int(acquired))
    await engine.dispose()
asyncio.run(main())
"""
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), 5)
        assert process.returncode == 0 and stdout.strip() == b"0"
    finally:
        release.set()
        assert await first
    assert len(delivered) == 1
    assert (await stored(integration_engine, command.message_id)).status == JobStatus.SENT
    assert not await Sender(sessions, settings, deliver, clock).run_once()


async def test_cancelled_sender_releases_mutex_and_reuses_frozen_mime(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    attempts: list[bytes] = []

    async def interrupted(email: PreparedEmail) -> None:
        attempts.append(email.data)
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await Sender(sessions, sender_settings, interrupted, clock).run_once()
    clock.now += timedelta(seconds=10)

    async def recovered(email: PreparedEmail) -> None:
        attempts.append(email.data)

    assert await Sender(sessions, sender_settings, recovered, clock).run_once()
    assert len(attempts) == 2 and attempts[0] == attempts[1]
    assert (await stored(integration_engine, command.message_id)).status == JobStatus.SENT


async def test_losing_postgresql_mutex_connection_cancels_inflight_sender(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    entered = asyncio.Event()
    attempts: list[bytes] = []

    async def interrupted(email: PreparedEmail) -> None:
        attempts.append(email.data)
        entered.set()
        await asyncio.Event().wait()

    settings = sender_settings.model_copy(update={"sender_timeout": 5.0})
    task = asyncio.create_task(Sender(sessions, settings, interrupted, clock).run_once())
    try:
        await asyncio.wait_for(entered.wait(), 3)
        async with integration_engine.connect() as connection:
            # Ordinary PostgreSQL roles may terminate their own other connections.
            assert await connection.scalar(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_locks "
                    "WHERE locktype='advisory' AND objid=794632801 AND granted "
                    "AND database=(SELECT oid FROM pg_database WHERE datname=current_database()) "
                    "AND pid<>pg_backend_pid()"
                )
            )
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    clock.now += timedelta(seconds=10)

    async def recovered(email: PreparedEmail) -> None:
        attempts.append(email.data)

    assert await Sender(sessions, settings, recovered, clock).run_once()
    assert len(attempts) == 2 and attempts[0] == attempts[1]
