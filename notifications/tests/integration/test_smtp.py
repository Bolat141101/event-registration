import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from notifications_app.config import Settings
from notifications_app.contract import NotificationMessage
from notifications_app.models import JobStatus
from notifications_app.sender import Sender
from notifications_app.smtp import send_email
from tests.integration.test_sender import Clock, stored
from tests.integration.test_sender import command as command
from tests.integration.test_sender import sender_settings as sender_settings

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@asynccontextmanager
async def smtp_server(mode: str) -> AsyncIterator[int]:
    async def receive(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            if mode == "stall":
                await reader.read()
                return
            writer.write(b"220 test SMTP\r\n")
            await writer.drain()
            while line := await reader.readline():
                if line.startswith(b"EHLO"):
                    writer.write(b"250-test\r\n250 SIZE 1000000\r\n")
                elif line.startswith(b"DATA"):
                    writer.write(b"354 send data\r\n")
                    await writer.drain()
                    await reader.readuntil(b"\r\n.\r\n")
                    if mode == "drop":
                        return
                    writer.write(b"451 private-token user@example.test\r\n")
                elif line.startswith(b"RCPT") and mode == "reject":
                    writer.write(b"550 private-token user@example.test\r\n")
                else:
                    writer.write(b"250 OK\r\n")
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(receive, "127.0.0.1", 0)
    async with server:
        yield server.sockets[0].getsockname()[1]


@pytest.mark.parametrize("mode", ["reject", "drop", "data", "stall"])
async def test_real_async_smtp_protocol_failures(
    integration_engine: AsyncEngine,
    command: NotificationMessage,
    sender_settings: Settings,
    mode: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with smtp_server(mode) as port:
        config = sender_settings.model_copy(update={"smtp_host": "127.0.0.1", "smtp_port": port})
        sender = Sender(
            async_sessionmaker(integration_engine),
            config,
            partial(send_email, settings=config),
            Clock(),
        )
        assert await asyncio.wait_for(sender.run_once(), timeout=2)
    row = await stored(integration_engine, command.message_id)
    assert row.mime is not None and row.attempts == 1
    assert row.status == (JobStatus.FAILED if mode == "reject" else JobStatus.PENDING)
    assert row.last_error and "private-token" not in row.last_error and "@" not in row.last_error
    assert "private-token" not in caplog.text and "user@example.test" not in caplog.text


async def test_real_mailpit_accept_then_local_crash_retry_has_same_message_id(
    integration_engine: AsyncEngine, command: NotificationMessage, sender_settings: Settings
) -> None:
    assert os.environ["SMTP_HOST"] == "test-mailpit"
    assert os.environ["TEST_MAILPIT_URL"] == "http://test-mailpit:8025"
    config = sender_settings.model_copy(update={"sender_timeout": 5})
    clock = Clock()
    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    sender = Sender(sessions, config, partial(send_email, settings=config), clock)
    with (
        patch.object(sender, "finish", side_effect=RuntimeError("crash after accept")),
        pytest.raises(RuntimeError),
    ):
        await sender.run_once()
    before = await stored(integration_engine, command.message_id)
    assert before.status == JobStatus.PENDING and before.mime
    clock.now = before.available_at
    await integration_engine.dispose()
    assert await Sender(sessions, config, partial(send_email, settings=config), clock).run_once()
    after = await stored(integration_engine, command.message_id)
    assert after.status == JobStatus.SENT and after.mime == before.mime and after.attempts == 2
    async with httpx.AsyncClient(base_url=os.environ["TEST_MAILPIT_URL"], trust_env=False) as http:
        messages = (await http.get("/api/v1/messages")).json()["messages"]
        matched = []
        for item in messages:
            response = await http.get(f"/api/v1/message/{item['ID']}/raw")
            if str(command.message_id).encode() in response.content:
                matched.append(response.content)
        assert (
            len(matched) == 1
        )  # Only this retained Mailpit store/config; not generic SMTP exactly-once.
        assert before.mime.split(b"\r\n\r\n", 1)[1] in matched[0]
