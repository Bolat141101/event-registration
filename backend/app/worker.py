"""Infrastructure probe only. Outbox delivery is a subsequent implementation stage."""

import logging
import signal
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db.health import database_is_ready, expected_schema_heads
from app.db.session import build_engine

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    engine = build_engine(settings)
    heads = expected_schema_heads()
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logger.info("Worker infrastructure started; email delivery is not implemented yet")
    try:
        while not stop.is_set():
            try:
                if not database_is_ready(engine, heads):
                    logger.error("Database schema is not ready")
            except SQLAlchemyError:
                logger.warning("Database is unavailable; retrying on next poll")
            stop.wait(settings.worker_poll_interval)
    finally:
        engine.dispose()
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
