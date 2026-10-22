from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.clock import as_utc

type UTCDateTime = Annotated[AwareDatetime, AfterValidator(as_utc)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateEvent(InputModel):
    description: str = Field(min_length=1, max_length=10000)
    starts_at: UTCDateTime
    capacity: int = Field(gt=0, le=2_147_483_647, strict=True)

    @field_validator("description")
    @classmethod
    def nonempty_description(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Описание не должно содержать нулевой символ")
        if not value.strip():
            raise ValueError("Описание не должно быть пустым")
        return value.strip()


class RescheduleEvent(InputModel):
    starts_at: UTCDateTime
    expected_schedule_version: int = Field(gt=0, le=2_147_483_647, strict=True)


class Register(InputModel):
    email: str = Field(min_length=1, max_length=320)


class ParticipationChange(InputModel):
    expected_participation_no: int = Field(gt=0, le=2_147_483_647, strict=True)


class CheckIn(InputModel):
    ticket_code: str = Field(min_length=1, max_length=256)


class RegistrationAccepted(BaseModel):
    message: str = "Если регистрация создана, сведения придут на почту"
