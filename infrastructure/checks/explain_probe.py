"""Isolated SQL plans with rollback-only fixture data; outputs plans, never email content."""

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import event as sql_event
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.session import build_engine
from app.services.events import reschedule_event


async def main() -> None:
    if not os.environ["LOAD_PROJECT"].startswith("event-registration-relay-check-ui-"):
        raise SystemExit("Isolated load project required")
    engine = build_engine(Settings())
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(
                        "INSERT INTO events(description,starts_at,capacity) "
                        "SELECT 'EXPLAIN fixture', CAST(:start AS timestamptz) "
                        "+ i * interval '1 second', 1 "
                        "FROM generate_series(1,10000) i"
                    ),
                    {"start": datetime.now(UTC) + timedelta(days=30)},
                )
                await connection.execute(text("ANALYZE events"))
                plans: dict[str, object] = {}
                for name, query in {
                    "bounded_page": "SELECT id FROM events ORDER BY starts_at,id LIMIT 21",
                    "page_aggregates": "SELECT e.id,count(r.id) FROM events e "
                    "LEFT JOIN registrations r ON r.event_id=e.id WHERE e.id IN "
                    "(SELECT id FROM events ORDER BY starts_at,id LIMIT 21) GROUP BY e.id",
                    "outbox_registration_lookup": "SELECT id FROM email_outbox "
                    "WHERE registration_id = :identity",
                }.items():
                    plans[name] = await connection.scalar(
                        text("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + query),
                        {"identity": uuid4()},
                    )
                if os.environ.get("LOAD_LABEL", "").startswith("after"):
                    row = (
                        await connection.execute(
                            text(
                                "SELECT id,starts_at,schedule_version FROM events "
                                "WHERE description LIKE 'Load probe %' LIMIT 1"
                            )
                        )
                    ).one()
                    compiled: list[tuple[str, Any]] = []

                    def capture(
                        _connection: Connection,
                        _cursor: Any,
                        statement: str,
                        parameters: Any,
                        _context: Any,
                        _many: bool,
                    ) -> None:
                        if statement.lstrip().startswith(
                            ("UPDATE email_outbox", "INSERT INTO email_outbox")
                        ):
                            compiled.append((statement, parameters))

                    savepoint = await connection.begin_nested()
                    sql_event.listen(connection.sync_connection, "before_cursor_execute", capture)
                    try:
                        async with AsyncSession(
                            bind=connection, join_transaction_mode="create_savepoint"
                        ) as session:
                            await reschedule_event(
                                session,
                                row.id,
                                row.starts_at + timedelta(days=1),
                                row.schedule_version,
                            )
                    finally:
                        sql_event.remove(
                            connection.sync_connection, "before_cursor_execute", capture
                        )
                        await savepoint.rollback()
                    assert len(compiled) == 3
                    for index, (statement, parameters) in enumerate(compiled):
                        savepoint = await connection.begin_nested()
                        try:
                            plan = await connection.exec_driver_sql(
                                "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + statement, parameters
                            )
                            plans[f"bulk_reschedule_{index + 1}"] = plan.scalar_one()
                        finally:
                            await savepoint.rollback()
                count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_schema='public' "
                        "AND table_name IN ('events','registrations','email_outbox')"
                    )
                )
                assert count == 24
                print(json.dumps({"plans": plans, "core_columns": count}, default=str))
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
