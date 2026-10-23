"""Pipe into a one-off worker container, only in an isolated Compose CI project.

Phases are orchestrated by CI: outage, recovery, lost HTTP response, process restart.
All database access here is to Core as its own application role; Notifications is
contacted solely over real HTTP. No Docker socket is mounted into the container.
"""

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import AnyHttpUrl
from sqlalchemy import select

from app.config import Settings
from app.db.models import EmailOutbox, Event, Registration
from app.db.session import build_engine, build_session_factory
from app.notifications.relay import Relay

LABEL = "HTTP relay smoke"


async def main(phase: str) -> None:
    project = os.environ["RELAY_SMOKE_PROJECT"]
    assert project == "event-registration-ci" or project.startswith(
        "event-registration-relay-check-"
    )
    settings = Settings()
    assert settings.database_url.hosts()[0]["host"] == "db"
    engine = build_engine(settings)
    sessions = build_session_factory(engine)
    token = settings.notifications_internal_token
    assert token is not None
    headers = {"Authorization": f"Bearer {token.get_secret_value()}"}
    query = (
        select(EmailOutbox)
        .join(Registration, EmailOutbox.registration_id == Registration.id)
        .join(Event, Registration.event_id == Event.id)
        .where(Event.description == LABEL, EmailOutbox.kind != "reminder")
    )
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as http:
            if phase in ("create", "lost-response"):
                response = await http.post(
                    "http://api:8000/api/events",
                    json={
                        "description": LABEL,
                        "starts_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                        "capacity": 1,
                    },
                    headers={
                        "Authorization": f"Bearer {settings.organizer_token.get_secret_value()}"
                    },
                )
                assert response.status_code == 201, response.status_code
                event_id = response.json()["id"]
                response = await http.post(
                    f"http://api:8000/api/events/{event_id}/registrations",
                    json={"email": "smoke@example.test"},
                )
                assert response.status_code == 202
            if phase == "outage":
                for _ in range(150):
                    async with sessions() as session:
                        rows = (
                            await session.scalars(query.where(EmailOutbox.status == "pending"))
                        ).all()
                    if rows and all(row.attempts > 0 and row.last_error for row in rows):
                        assert all(row.status == "pending" and row.prepared_at for row in rows)
                        print("PASS outage: Core transaction committed, jobs retained for retry")
                        break
                    await asyncio.sleep(0.2)
                else:
                    raise AssertionError(
                        "Relay did not persist retry state during recipient outage"
                    )
            elif phase == "recover":
                for _ in range(150):
                    async with sessions() as session:
                        rows = (await session.scalars(query)).all()
                    if rows and all(row.status == "forwarded" for row in rows):
                        print(
                            f"PASS recovery: {len(rows)} HTTP-accepted jobs; none marked SMTP sent"
                        )
                        break
                    await asyncio.sleep(0.2)
                else:
                    raise AssertionError("Persisted jobs did not recover after restart")
                for row in rows:
                    responses = await asyncio.gather(
                        *(
                            http.post(
                                "http://notifications:8000/internal/v1/notifications",
                                json=row.payload,
                                headers=headers,
                            )
                            for _ in range(8)
                        )
                    )
                    assert all(response.status_code == 202 for response in responses)
                    changed = {
                        **row.payload,
                        "payload": {**row.payload["payload"], "description": "conflict"},
                    }
                    assert (
                        await http.post(
                            "http://notifications:8000/internal/v1/notifications",
                            json=changed,
                            headers=headers,
                        )
                    ).status_code == 409
                assert (
                    await http.post(
                        "http://notifications:8000/internal/v1/notifications", json=rows[0].payload
                    )
                ).status_code == 401
                print(
                    "PASS real HTTP: concurrent duplicates=202, "
                    "conflicting document=409, no token=401"
                )
            elif phase == "lost-response":
                committed = asyncio.Event()

                async def discard_ack(
                    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
                ) -> None:
                    try:
                        head = await reader.readuntil(b"\r\n\r\n")
                        length = next(
                            int(line.split(b":", 1)[1])
                            for line in head.split(b"\r\n")
                            if line.lower().startswith(b"content-length:")
                        )
                        body = await reader.readexactly(length)
                        response = await http.post(
                            "http://notifications:8000/internal/v1/notifications",
                            content=body,
                            headers={**headers, "Content-Type": "application/json"},
                        )
                        assert response.status_code == 202
                        committed.set()
                        # Close the TCP connection AFTER the receiver's commit/202,
                        # without returning any status line to the Core client.
                    finally:
                        writer.close()
                        await writer.wait_closed()

                server = await asyncio.start_server(discard_ack, "127.0.0.1", 0)
                port = server.sockets[0].getsockname()[1]
                async with server:
                    proxy_settings = settings.model_copy(
                        update={"notifications_url": AnyHttpUrl(f"http://127.0.0.1:{port}")}
                    )
                    assert await Relay(sessions, http, proxy_settings).run_once()
                    await asyncio.wait_for(committed.wait(), timeout=5)
                async with sessions() as session:
                    rows = (await session.scalars(query.where(Event.id == event_id))).all()
                assert len(rows) == 1 and rows[0].status == "pending" and rows[0].attempts == 1
                print("PASS real TCP response loss after receiver commit: pending retry retained")
            elif phase != "create":
                raise ValueError("Unknown smoke phase")
            if phase == "create":
                print("PASS Core API while Notifications stopped: event=201, registration=202")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
