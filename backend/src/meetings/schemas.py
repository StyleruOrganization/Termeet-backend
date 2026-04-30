from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SlotsUser(BaseModel):
    name: str
    slots: list[list[str]]


class Meet(BaseModel):
    name: str
    description: str | None = None
    link: str | None = None
    duration: str | None = None
    dataRange: list[list[str]] = Field(alias="data_range")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MeetCreate(Meet):
    pass


class MeetResponse(Meet):
    hash: UUID = Field(validation_alias="id")
    slots: list[SlotsUser] = []

    @field_validator("slots", mode="before")
    @classmethod
    def validate_slots(cls, value):
        return [
            SlotsUser(name=key, slots=value)
            for slot in value
            for key, value in slot.items()
            if key != "user_id"
        ]
