"""Operator-only queue summary. Never print payloads, recipients, MIME or exception text."""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.config import Settings
from app.db.models import EmailOutbox
from app.db.session import build_engine, build_session_factory


async def summary() -> dict[str, object]:
    engine = build_engine(Settings())
    try:
        async with build_session_factory(engine)() as session:
            counts = {
                status.value: count
                for status, count in (
                    await session.execute(
                        select(EmailOutbox.status, func.count()).group_by(EmailOutbox.status)
                    )
                ).all()
            }
            due = await session.scalar(
                select(func.min(EmailOutbox.available_at)).where(
                    EmailOutbox.status == "pending", EmailOutbox.available_at <= datetime.now(UTC)
                )
            )
            failed = list(
                (
                    await session.scalars(
                        select(EmailOutbox.id)
                        .where(EmailOutbox.status == "failed")
                        .order_by(EmailOutbox.id)
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
