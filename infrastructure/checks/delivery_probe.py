"""Measure isolated backlog recovery with real relay, sender and Mailpit."""

import asyncio
import json
import os
import time

import httpx
from sqlalchemy import text

from app.config import Settings
from app.db.session import build_engine


async def main() -> None:
    if not os.environ["LOAD_PROJECT"].startswith("event-registration-relay-check-ui-"):
        raise SystemExit("Isolated project required")
    engine = build_engine(Settings())
    started, maximum_age = float(os.environ.get("LOAD_DRAIN_STARTED", time.time())), 0.0
    try:
        async with httpx.AsyncClient(timeout=5) as client, asyncio.timeout(180):
            while True:
                async with engine.connect() as connection:
                    row = (
                        await connection.execute(
                            text(
                                "SELECT count(*) FILTER "
                                "(WHERE status='pending' AND available_at<=now()), "
                                "count(*) FILTER (WHERE status='failed'), "
                                "count(*) FILTER (WHERE status='forwarded'), "
                                "coalesce(extract(epoch FROM now()-min(available_at) FILTER "
                                "(WHERE status='pending' AND available_at<=now())),0) "
                                "FROM email_outbox"
                            )
                        )
                    ).one()
                maximum_age = max(maximum_age, float(row[3]))
                assert row[1] == 0
                total = (await client.get("http://mailpit:8025/api/v1/messages")).json()["total"]
                if row[0] == 0 and row[2] > 0 and total >= row[2]:
                    print(
                        json.dumps(
                            {
                                "drain_seconds": round(time.time() - started, 3),
                                "max_oldest_due_seconds": round(maximum_age, 3),
                                "forwarded": row[2],
                                "mailpit_messages": total,
                                "core_failed": row[1],
                            }
                        )
                    )
                    break
                await asyncio.sleep(0.5)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
