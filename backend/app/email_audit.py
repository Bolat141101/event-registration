"""Read-only preflight for operators. Report row IDs, never email/token values."""

import asyncio
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.db.session import build_engine
from app.email_addresses import canonical_email


@dataclass(frozen=True)
class EmailAudit:
    total: int
    changed: int
    invalid_ids: list[UUID]
    collision_groups: list[list[UUID]]


async def audit(engine: AsyncEngine) -> EmailAudit:
    async with engine.connect() as connection, connection.begin():
        await connection.execute(text("SET TRANSACTION READ ONLY"))
        rows = (
            await connection.execute(
                text("SELECT id,event_id,email FROM registrations ORDER BY id")
            )
        ).all()
    groups: dict[tuple[UUID, str], list[UUID]] = defaultdict(list)
    changed, invalid = 0, []
    for identity, event, address in rows:
        try:
            canonical = canonical_email(address)
        except ValueError:
            invalid.append(identity)
            continue
        changed += address != canonical
        groups[(event, canonical)].append(identity)
    return EmailAudit(len(rows), changed, invalid, [ids for ids in groups.values() if len(ids) > 1])


async def main() -> None:
    engine = build_engine(Settings())
    try:
        report = await audit(engine)
        print(json.dumps(asdict(report), default=str))
        if report.invalid_ids or report.collision_groups:
            raise SystemExit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
