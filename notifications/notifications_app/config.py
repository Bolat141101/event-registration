from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from notifications_app.mime import mailbox


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: PostgresDsn = Field(repr=False)
    notifications_internal_token: SecretStr = Field(min_length=32)

    smtp_host: str = Field(default="mailpit", min_length=1)
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_from: str = Field(default="events@example.test", repr=False)
    public_app_url: AnyHttpUrl = Field(default=AnyHttpUrl("http://localhost:8080"), repr=False)
    sender_timeout: float = Field(default=5, gt=0, le=60)
    sender_poll_interval: float = Field(default=5, gt=0, le=60)
    sender_max_attempts: int = Field(default=8, ge=1, le=100)
    sender_backoff_base: float = Field(default=1, gt=0, le=3600)
    sender_backoff_cap: float = Field(default=60, gt=0, le=86400)

    @field_validator("smtp_from")
    @classmethod
    def valid_sender(cls, value: str) -> str:
        return mailbox(value)

    @field_validator("public_app_url")
    @classmethod
    def public_origin(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username or value.password or value.query or value.fragment or value.path != "/":
            raise ValueError("PUBLIC_APP_URL must be an HTTP(S) origin")
        return value

    @field_validator("database_url")
    @classmethod
    def require_asyncpg(cls, value: PostgresDsn) -> PostgresDsn:
        if value.scheme != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        return value
