"""Run only in isolated CI, in Notifications' one-off sender container.

Own DB + real Mailpit; SMTP proxy drops the reply after the real DATA accept.
"""

import asyncio
import json
import os
import sys
import urllib.request
from email import policy
from email.parser import BytesParser
from functools import partial
from typing import Any, cast

from notifications_app.config import Settings
from notifications_app.contract import NotificationMessage
from notifications_app.db import build_engine, build_session_factory
from notifications_app.mime import load_prepared
from notifications_app.models import NotificationJob
from notifications_app.sender import Sender
from notifications_app.smtp import send_email
from sqlalchemy import select

LABEL = "HTTP relay smoke"


async def mailpit(path: str) -> bytes:
    def get() -> bytes:
        with urllib.request.urlopen(f"http://mailpit:8025{path}", timeout=5) as response:
            data = response.read()
            assert isinstance(data, bytes)
            return data

    return await asyncio.to_thread(get)


async def main(phase: str) -> None:
    project = os.environ["RELAY_SMOKE_PROJECT"]
    assert project == "event-registration-ci" or project.startswith(
        "event-registration-relay-check-"
    )
    settings = Settings()
    assert settings.smtp_host == "mailpit"
    assert settings.database_url.hosts()[0]["host"] == "db"
    engine = build_engine(settings)
    sessions = build_session_factory(engine)
    query = select(NotificationJob).where(
        NotificationJob.payload["payload"]["description"].astext == LABEL,
        NotificationJob.payload["kind"].astext != "reminder",
    )

    async def rows() -> list[NotificationJob]:
        async with sessions() as session:
            return list((await session.scalars(query)).all())

    try:
        if phase == "outage":
            async with asyncio.timeout(30):
                while True:
                    pending = [job for job in await rows() if job.status == "pending"]
                    if pending and all(
                        job.mime and job.attempts > 0 and job.last_error for job in pending
                    ):
                        print(
                            "PASS SMTP outage: pending jobs, MIME and retry state durably retained"
                        )
                        return
                    await asyncio.sleep(0.2)
        elif phase == "recover":
            async with asyncio.timeout(30):
                while True:
                    jobs = await rows()
                    if jobs and all(job.status == "sent" for job in jobs):
                        break
                    await asyncio.sleep(0.2)
            listing = cast(dict[str, Any], json.loads(await mailpit("/api/v1/messages")))
            sources = [
                await mailpit(f"/api/v1/message/{item['ID']}/raw") for item in listing["messages"]
            ]
            for job in jobs:
                matched = [raw for raw in sources if str(job.id).encode() in raw]
                assert len(matched) == 1 and job.mime is not None
                frozen = BytesParser(policy=policy.default).parsebytes(job.mime)
                received = BytesParser(policy=policy.default).parsebytes(matched[0])
                for name in ("To", "From", "Date", "Message-ID", "Subject"):
                    assert str(frozen[name]) == str(received[name])
                assert frozen.get_payload(decode=True) == received.get_payload(decode=True)
            print(f"PASS SMTP recovery: {len(jobs)} sent jobs; frozen MIME matches Mailpit")
        elif phase == "lost-response":
            async with asyncio.timeout(30):
                while True:
                    pending = [job for job in await rows() if job.status == "pending"]
                    if pending:
                        break
                    await asyncio.sleep(0.2)
            assert len(pending) == 1 and pending[0].attempts == 0
            identity = pending[0].id
            committed = asyncio.Event()
            errors: list[str] = []

            async def discard_ack(
                reader: asyncio.StreamReader, writer: asyncio.StreamWriter
            ) -> None:
                try:
                    writer.write(b"220 test proxy\r\n")
                    await writer.drain()
                    while line := await reader.readline():
                        if line.startswith(b"EHLO"):
                            writer.write(b"250-proxy\r\n250 SIZE 1000000\r\n")
                        elif line.startswith(b"DATA"):
                            writer.write(b"354 send data\r\n")
                            await writer.drain()
                            wire = await reader.readuntil(b"\r\n.\r\n")
                            data = wire[:-3].replace(b"\r\n..", b"\r\n.")
                            jobs = await rows()
                            job = next(item for item in jobs if item.id == identity)
                            command = NotificationMessage.model_validate(job.payload)
                            assert job.mime == data
                            await send_email(load_prepared(command, data), settings=settings)
                            committed.set()  # Mailpit accepted, but NO 250 sent back to sender.
                            return
                        else:
                            writer.write(b"250 OK\r\n")
                        await writer.drain()
                except Exception as exc:
                    errors.append(type(exc).__name__)
                finally:
                    writer.close()
                    await writer.wait_closed()

            server = await asyncio.start_server(discard_ack, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            config = settings.model_copy(update={"smtp_host": "127.0.0.1", "smtp_port": port})
            async with server:
                assert await Sender(
                    sessions, config, partial(send_email, settings=config)
                ).run_once()
                await asyncio.wait_for(committed.wait(), timeout=5)
            assert not errors, errors
            job = next(item for item in await rows() if item.id == identity)
            assert job.status == "pending" and job.attempts == 1 and job.mime and job.last_error
            print(
                "PASS real SMTP DATA response loss after Mailpit accept: pending retry, frozen MIME"
            )
        else:
            raise ValueError("Unknown smoke phase")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
