"""Three set-based statements in the caller's event-locked transaction.

Keep exactly the same freeze/dedup/reminder rules as single-participant operations.
Parameters are typed explicitly because jsonb_build_object is polymorphic.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Integer, Text, Uuid, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import TypeEngine

from app.db.models import Event

_CONTEXT = """jsonb_build_object(
    'recipient', r.email, 'event_id', CAST(:event_id AS text),
    'description', CAST(:description AS text), 'starts_at', CAST(:starts_at AS text),
    'schedule_version', CAST(:version AS integer), 'participation_no', r.participation_no,
    'registration_status', r.status, 'ticket_code', r.ticket_code)"""
_ACTIVE = "r.event_id = :event_id AND r.status <> 'cancelled'"


async def queue_reschedules(
    session: AsyncSession, event: Event, old_starts_at: datetime, now: datetime
) -> None:
    types: dict[str, TypeEngine[Any]] = {
        "event_id": Uuid(),
        "description": Text(),
        "starts_at": Text(),
        "version": Integer(),
        "old_starts_at": Text(),
        "now": DateTime(timezone=True),
        "deadline": DateTime(timezone=True),
    }

    async def execute(query: str) -> None:
        statement = text(query).bindparams(
            *(bindparam(key, type_=kind) for key, kind in types.items() if ":" + key in query)
        )
        await session.execute(statement, parameters)

    parameters = {
        "event_id": event.id,
        "description": event.description,
        "starts_at": event.starts_at.isoformat(),
        "version": event.schedule_version,
        "old_starts_at": old_starts_at.isoformat(),
        "now": now,
        "deadline": max(now, event.starts_at - timedelta(hours=24)),
    }
    await execute(f"""
        UPDATE email_outbox o SET
          status = CASE WHEN o.payload->'participation_no' IS DISTINCT FROM
          to_jsonb(r.participation_no)
                        THEN 'cancelled' ELSE o.status END,
          payload = CASE WHEN o.payload->'participation_no' IS DISTINCT FROM
          to_jsonb(r.participation_no)
                    THEN o.payload ELSE {_CONTEXT}
                      || CASE WHEN o.kind='waitlist' THEN jsonb_build_object('ticket_code',NULL)
                      ELSE
                      '{{}}'::jsonb END
                      || CASE WHEN o.payload ? 'manage_path' THEN
                      jsonb_build_object('manage_path', o.payload->'manage_path') ELSE
                      '{{}}'::jsonb END END
        FROM registrations r WHERE o.registration_id=r.id AND {_ACTIVE}
          AND o.prepared_at IS NULL AND o.kind IN ('ticket','waitlist')
          AND o.status IN ('pending','failed')
    """)
    await execute(f"""
        INSERT INTO email_outbox (registration_id,kind,dedup_key,payload,available_at)
        SELECT r.id,'reminder','reminder:' || r.id::text,{_CONTEXT},:deadline
        FROM registrations r WHERE {_ACTIVE}
        ON CONFLICT (dedup_key) DO UPDATE SET payload=excluded.payload,
          available_at=excluded.available_at,
          status=CASE WHEN email_outbox.status='cancelled' THEN 'pending' ELSE email_outbox.status
          END
        WHERE email_outbox.prepared_at IS NULL
    """)
    await execute(f"""
        INSERT INTO email_outbox (registration_id,kind,dedup_key,payload,available_at)
        SELECT r.id,'rescheduled','rescheduled:' || r.id::text || ':' || CAST(:version AS text),
          {_CONTEXT} || jsonb_build_object('old_starts_at',CAST(:old_starts_at AS text),
                                          'new_starts_at',CAST(:starts_at AS text)),:now
        FROM registrations r WHERE {_ACTIVE} ON CONFLICT (dedup_key) DO NOTHING
    """)
