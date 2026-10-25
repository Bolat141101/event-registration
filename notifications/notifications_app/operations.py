"""Operator-only queue summary. Never print payloads, recipients, MIME or exception text."""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import func, select

from notifications_app.config import Settings
from notifications_app.db import build_engine, build_session_factory
from notifications_app.models import NotificationJob


async def summary() -> dict[str, object]:
    engine = build_engine(Settings())
    try:
        async with build_session_factory(engine)() as session:
            counts = {
                status.value: count
                for status, count in (
                    await session.execute(
                        select(NotificationJob.status, func.count()).group_by(
                            NotificationJob.status
                        )
                    )
                ).all()
            }
            due = await session.scalar(
                select(func.min(NotificationJob.available_at)).where(
                    NotificationJob.status == "pending",
                    NotificationJob.available_at <= datetime.now(UTC),
                )
            )
            failed = list(
                (
                    await session.scalars(
                        select(NotificationJob.id)
                        .where(NotificationJob.status == "failed")
                        .order_by(NotificationJob.id)
                        .limit(20)
                    )
                ).all()
            )
        return {
            "counts": counts,
            "oldest_due_seconds": max(0, (datetime.now(UTC) - due).total_seconds()) if due else 0,
            "failed_ids_sample": [str(identity) for identity in failed],
        }
    finally:
        await engine.dispose()


async def main(check: bool) -> None:
    result = await summary()
    print(json.dumps(result, sort_keys=True))
    counts = result["counts"]
    assert isinstance(counts, dict)
    age = result["oldest_due_seconds"]
    assert isinstance(age, (int, float))
    if check and (counts.get("failed", 0) > 0 or age > 60):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Exit 1 for failed jobs or overdue work >60s"
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.check))
