"""Run exactly one sender process, independent of the HTTP API and Core."""

import asyncio
import logging
import signal
from contextlib import suppress
from functools import partial

from notifications_app.config import Settings
from notifications_app.db import build_engine, build_session_factory
from notifications_app.health import database_is_ready, expected_schema_heads
from notifications_app.sender import Sender
from notifications_app.smtp import send_email
from notifications_app.worker_health import heartbeat

logger = logging.getLogger(__name__)


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    engine = build_engine(settings)
    heads = expected_schema_heads()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    logger.info("Notifications SMTP sender started (one sequential process)")
    try:
        sender = Sender(
            build_session_factory(engine), settings, partial(send_email, settings=settings)
        )
        while not stop.is_set():
            try:
                ready = await database_is_ready(engine, heads)
                heartbeat(ready)
                if not ready:
                    logger.error("Notifications database schema is not ready")
                elif await sender.run_once():
                    continue
            except Exception as exc:
                heartbeat(False)
                # Exception strings may contain DSN, recipient, token or SMTP replies.
                logger.warning("Sender iteration failed (%s)", type(exc).__name__)
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.sender_poll_interval)
    finally:
        await engine.dispose()
        logger.info("Notifications sender stopped")


if __name__ == "__main__":
    asyncio.run(run())
