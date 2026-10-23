"""Durably accept immutable commands; never access Core or send SMTP."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from notifications_app.contract import NotificationMessage
from notifications_app.models import NotificationJob


class MessageConflict(Exception):
    pass


async def accept_message(session: AsyncSession, message: NotificationMessage) -> None:
    document = message.model_dump(mode="json")
    async with session.begin():
        inserted = await session.scalar(
            insert(NotificationJob)
            .values(id=message.message_id, payload=document)
            .on_conflict_do_nothing(index_elements=[NotificationJob.id])
            .returning(NotificationJob.id)
        )
        if inserted is None:
            # A competing INSERT waits on the PK. This new READ COMMITTED statement
            # sees its committed document; never update a previously accepted job.
            existing = await session.scalar(
                select(NotificationJob.payload).where(NotificationJob.id == message.message_id)
            )
            if existing != document:
                raise MessageConflict
    # Returning means commit completed, not merely that INSERT was flushed.
