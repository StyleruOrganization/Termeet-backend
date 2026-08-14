from uuid import UUID
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class AvailabilityInterval(BaseModel):
    weekday: int | None = Field(None, ge=1, le=7)
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")

    @field_validator("start")
    @classmethod
    def valid_start(cls, value: str) -> str:
        hours, minutes = value.split(":")
        if int(hours) > 23 or minutes not in ("00", "30"):
            raise ValueError("start must be HH:00 or HH:30")
        return value

    @field_validator("end")
    @classmethod
    def valid_end(cls, value: str, info) -> str:
        hours, minutes = value.split(":")
        is_midnight = value == "24:00"
        if not is_midnight and (
            int(hours) > 23 or minutes not in ("00", "30")
        ):
            raise ValueError("end must be HH:00, HH:30 or 24:00")
        start = info.data.get("start")
        if start and value <= start:
            raise ValueError("end must be later than start")
        return value


class UserSchema(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    nickname: Optional[str]
    is_active: bool
    is_verified: bool
    email: str
    additional_emails: Optional[list]
    timezone: str = "UTC +3:00 (Москва)"
    theme: str = "light"
    suggest_prefill: bool = True
    availability_template: list[AvailabilityInterval] = Field(
        default_factory=list
    )
    locale: str = "ru"
    grid_window_start: str = "10 : 00"
    grid_window_end: str = "19 : 00"

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def from_orm_without_computed_nickname(cls, data):
        if not hasattr(data, "__table__"):
            return data
        return {
            "id": data.id,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "nickname": data.first_name,
            "is_active": data.is_active,
            "is_verified": data.is_verified,
            "email": data.email,
            "additional_emails": data.additional_emails,
            "timezone": getattr(data, "timezone", "UTC +3:00 (Москва)"),
            "theme": getattr(data, "theme", "light"),
            "suggest_prefill": getattr(data, "suggest_prefill", True),
            "availability_template": getattr(
                data, "availability_template", []
            )
            or [],
            "locale": getattr(data, "locale", "ru") or "ru",
            "grid_window_start": getattr(
                data, "grid_window_start", "10 : 00"
            )
            or "10 : 00",
            "grid_window_end": getattr(
                data, "grid_window_end", "19 : 00"
            )
            or "19 : 00",
        }


class UserSettingsUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    timezone: str | None = Field(None, max_length=64)
    theme: Literal["light", "dark"] | None = None
    suggest_prefill: bool | None = None
    availability_template: list[AvailabilityInterval] | None = None
    locale: Literal["ru", "en", "de"] | None = None
    grid_window_start: str | None = Field(None, max_length=16)
    grid_window_end: str | None = Field(None, max_length=16)

    model_config = ConfigDict(extra="ignore")

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("availability_template")
    @classmethod
    def limit_template(cls, value):
        if value is not None and len(value) > 200:
            raise ValueError("Слишком много интервалов в шаблоне")
        return value


class UserSearchItem(BaseModel):
    id: UUID
    first_name: str
    last_name: str

