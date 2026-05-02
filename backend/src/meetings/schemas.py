from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SlotsUser(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    user_id: UUID | None = Field(None, alias="userId")
    slots: list[list[str]]


class Meet(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=400)
    link: str | None = Field(None, max_length=128)
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
    def validate_slots(cls, slots_db):
        return [
            SlotsUser(
                name=slot["name"], userId=slot["user_id"], slots=slot["slots"]
            )
            for slot in slots_db
        ]


class CheckAccessRights(BaseModel):
    is_creator: bool
    is_creator_auth: bool
