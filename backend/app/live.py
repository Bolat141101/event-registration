"""One database snapshot per event/process, shared by bounded SSE subscribers."""

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from uuid import UUID

from anyio import CancelScope
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import events
from app.services.common import EventView
from app.services.errors import DomainError

logger = logging.getLogger(__name__)


async def read_event(sessions: async_sessionmaker[AsyncSession], event_id: UUID) -> EventView:
    with CancelScope(shield=True):
        async with sessions() as session:
            return await events.get_event(session, event_id)
    raise asyncio.CancelledError


@dataclass
class Topic:
    ready: asyncio.Future[EventView]
    queues: set[asyncio.Queue[EventView | None]] = field(default_factory=set)
    latest: EventView | None = None
    task: asyncio.Task[None] | None = None


class Subscription:
    def __init__(
        self, hub: "LiveHub", identity: UUID, topic: Topic, queue: asyncio.Queue[EventView | None]
    ) -> None:
        self.hub, self.identity, self.topic, self.queue = hub, identity, topic, queue
        self.closed = False

    async def close(self) -> None:
        with CancelScope(shield=True):
            if self.closed:
                return
            self.closed = True
            self.topic.queues.discard(self.queue)
            self.hub.subscribers -= 1
            if not self.topic.queues:
                if self.hub.topics.get(self.identity) is self.topic:
                    del self.hub.topics[self.identity]
                if self.topic.task:
                    self.topic.task.cancel()
                    with suppress(asyncio.CancelledError):
                        await self.topic.task


class LiveHub:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], limit: int = 2000) -> None:
        self.sessions, self.limit = sessions, limit
        self.topics: dict[UUID, Topic] = {}
        self.subscribers = 0
        self.reads = 0

    async def subscribe(self, identity: UUID) -> Subscription:
        # Local admission bound only; all business decisions still use PostgreSQL.
        if self.subscribers >= self.limit:
            raise LiveCapacityError
        topic = self.topics.get(identity)
        if topic is None:
            topic = Topic(asyncio.get_running_loop().create_future())
            self.topics[identity] = topic
            topic.task = asyncio.create_task(self._produce(identity, topic))
        queue: asyncio.Queue[EventView | None] = asyncio.Queue(maxsize=1)
        topic.queues.add(queue)
        self.subscribers += 1
        subscription = Subscription(self, identity, topic, queue)
        if topic.latest is not None:
            queue.put_nowait(topic.latest)
        try:
            await asyncio.shield(topic.ready)  # One disconnect must not cancel other waiters.
        except BaseException:
            await subscription.close()
            raise
        return subscription

    def _broadcast(self, topic: Topic, snapshot: EventView | None) -> None:
        for queue in topic.queues:
            if queue.full():
                queue.get_nowait()  # This is current state, not an event replay log.
            queue.put_nowait(snapshot)

    async def _produce(self, identity: UUID, topic: Topic) -> None:
        try:
            while True:
                snapshot = await read_event(self.sessions, identity)
                self.reads += 1
                topic.latest = snapshot
                if not topic.ready.done():
                    topic.ready.set_result(snapshot)
                self._broadcast(topic, snapshot)
                await asyncio.sleep(1)
        except (DomainError, SQLAlchemyError, OSError) as exc:
            if not topic.ready.done():
                topic.ready.set_exception(exc)  # 404/503 before the first response headers.
            else:
                logger.warning("Live snapshot unavailable; closing subscribers")
                self._broadcast(topic, None)
        finally:
            # Retire before old HTTP subscribers finish closing: a reconnect must
            # create a producer, never attach to a completed Future/cached snapshot.
            if self.topics.get(identity) is topic:
                del self.topics[identity]
            if not topic.ready.done():
                topic.ready.cancel()

    async def close(self) -> None:
        tasks = [topic.task for topic in self.topics.values() if topic.task]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.topics.clear()


class LiveCapacityError(Exception):
    pass
