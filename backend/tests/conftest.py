import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/event_registration_test",
        organizer_token="test_organizer_token_at_least_32_characters",
    )


@pytest.fixture(scope="session")
def integration_engine() -> Iterator[Engine]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    url = make_url(database_url)
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("Integration tests require a dedicated database whose name ends in _test")
    if url.get_backend_name() != "postgresql":
        pytest.fail("Integration tests must run against PostgreSQL")
    engine = create_engine(url, isolation_level="READ COMMITTED")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(integration_engine: Engine) -> Iterator[Session]:
    with integration_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
