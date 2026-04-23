from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SlotsUser(BaseModel):
    name: str
    slots: list[list[str]]


class Meet(BaseModel):
    name: str
    description: str | None = None
    link: str | None = None
    duration: str | None = None
    dataRange: list[list[str]] = Field(validation_alias="data_range")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MeetCreate(Meet):
    pass


class MeetResponse(Meet):
    hash: UUID = Field(validation_alias="id")  # ПРОВЕРЬ
    slots: list[SlotsUser] = []
