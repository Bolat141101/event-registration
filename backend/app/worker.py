"""One sequential asynchronous HTTP relay; SMTP belongs to Notifications."""

import asyncio
import logging
import signal
from contextlib import suppress

import httpx

from app.config import Settings
from app.db.health import database_is_ready, expected_schema_heads
from app.db.session import build_engine, build_session_factory
from app.notifications.relay import Relay

logger = logging.getLogger(__name__)


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    if settings.notifications_internal_token is None:
        raise ValueError("NOTIFICATIONS_INTERNAL_TOKEN is required for the relay")
    engine = build_engine(settings)
    heads = expected_schema_heads()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    logger.info("Core HTTP relay started (one sequential process); SMTP is not implemented")
    try:
        async with httpx.AsyncClient(
            trust_env=False, limits=httpx.Limits(max_connections=1, max_keepalive_connections=1)
        ) as client:
            relay = Relay(build_session_factory(engine), client, settings)
            while not stop.is_set():
                try:
                    if not await database_is_ready(engine, heads):
                        logger.error("Database schema is not ready")
                    elif await relay.run_once():
                        continue
                except Exception as exc:
                    # DB failures may escape asyncpg without a SQLAlchemy wrapper.
                    # Retry the durable state on a later poll; never log credentials.
                    logger.warning("Relay iteration failed (%s)", type(exc).__name__)
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval)
    finally:
        await engine.dispose()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(run())
