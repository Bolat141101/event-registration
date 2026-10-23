"""Wire protocol v1. Kept compatible with Notifications and the checked-in JSON Schema."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def reject_null_character(cls, value: object) -> object:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Null characters are forbidden")
        return value


class NotificationPayload(WireModel):
    recipient: str = Field(min_length=3, max_length=320)
    event_id: UUID
    description: str = Field(min_length=1, max_length=10000)
    starts_at: AwareDatetime
    schedule_version: int = Field(gt=0, le=2_147_483_647, strict=True)
    participation_no: int = Field(gt=0, le=2_147_483_647, strict=True)
    registration_status: Literal["confirmed", "waitlisted"]
    ticket_code: str | None = Field(default=None, min_length=1, max_length=256)
    manage_path: str | None = Field(
        default=None, max_length=512, pattern=r"^/registration#token=[A-Za-z0-9_-]+$"
    )
    old_starts_at: AwareDatetime | None = None
    new_starts_at: AwareDatetime | None = None

    @field_validator("starts_at", "old_starts_at", "new_starts_at", mode="before")
    @classmethod
    def iso_dates(cls, value: object) -> object:
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("Dates must use ISO 8601 strings")
        if isinstance(value, str) and "T" not in value.upper():
            raise ValueError("Dates must use ISO 8601 strings")
        return value

    @field_validator("starts_at", "old_starts_at", "new_starts_at")
    @classmethod
    def utc_dates(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        try:
            return value.astimezone(UTC)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Date is outside the UTC range") from exc


class NotificationMessage(WireModel):
    schema_version: Literal[1]
    message_id: UUID
    registration_id: UUID
    kind: Literal["ticket", "waitlist", "reminder", "rescheduled"]
    payload: NotificationPayload

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be the integer 1")
        return value

    @model_validator(mode="after")
    def consistent_notice(self) -> "NotificationMessage":
        body = self.payload
        if self.kind == "ticket" and (
            body.registration_status != "confirmed" or not body.ticket_code
        ):
            raise ValueError("Ticket requires confirmed participation and a ticket code")
        if self.kind == "waitlist" and body.ticket_code is not None:
            raise ValueError("Waitlist notice must not contain a ticket")
        if self.kind == "rescheduled":
            if (
                body.old_starts_at is None
                or body.new_starts_at != body.starts_at
                or body.old_starts_at == body.new_starts_at
            ):
                raise ValueError(
                    "Reschedule requires distinct old/new dates and matching starts_at"
                )
        elif body.old_starts_at is not None or body.new_starts_at is not None:
            raise ValueError("Old/new dates are only valid for rescheduled notices")
        return self


class NotificationAccepted(WireModel):
    message_id: UUID
    status: Literal["accepted"]
