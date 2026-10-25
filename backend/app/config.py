from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: PostgresDsn = Field(repr=False)
    organizer_token: SecretStr = Field(min_length=32, repr=False)
    sse_max_connections: int = Field(default=2000, ge=1, le=10000)
    worker_poll_interval: float = Field(default=5.0, gt=0, le=60)
    notifications_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://notifications:8000"), repr=False
    )
    notifications_internal_token: SecretStr | None = Field(default=None, min_length=32, repr=False)
    relay_timeout: float = Field(default=5, gt=0, le=30)
    relay_max_attempts: int = Field(default=8, ge=1, le=100)
    relay_backoff_base: float = Field(default=1, gt=0, le=60)
    relay_backoff_cap: float = Field(default=60, gt=0, le=3600)
    relay_candidate_limit: int = Field(default=20, ge=1, le=100)

    @field_validator("database_url")
    @classmethod
    def require_asyncpg(cls, value: PostgresDsn) -> PostgresDsn:
        if value.scheme != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        return value
