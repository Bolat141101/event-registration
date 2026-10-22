from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        str(settings.database_url),
        isolation_level="READ COMMITTED",
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "timeout": 3,
            "server_settings": {"lock_timeout": "2000", "statement_timeout": "3000"},
        },
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False)
