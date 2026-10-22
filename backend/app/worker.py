"""Infrastructure probe only. Outbox delivery is a subsequent implementation stage."""

import asyncio
import logging
import signal
from contextlib import suppress

from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db.health import database_is_ready, expected_schema_heads
from app.db.session import build_engine

logger = logging.getLogger(__name__)


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    engine = build_engine(settings)
    heads = expected_schema_heads()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    logger.info("Worker infrastructure started; email delivery is not implemented yet")
    try:
        while not stop.is_set():
            try:
                if not await database_is_ready(engine, heads):
                    logger.error("Database schema is not ready")
            except (SQLAlchemyError, OSError, TimeoutError):
                logger.warning("Database is unavailable; retrying on next poll")
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval)
    finally:
        await engine.dispose()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(run())
