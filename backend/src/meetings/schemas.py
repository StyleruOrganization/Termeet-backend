from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SlotsUser(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    user_id: UUID | None = Field(None, alias="userId")
    slots: list[list[str]]
    is_auth: bool = Field(False, alias="isAuth")

    model_config = ConfigDict(populate_by_name=True)


class ObserverUser(BaseModel):
    name: str
    user_id: str | None = Field(None, alias="userId")

    model_config = ConfigDict(populate_by_name=True)


class MeetPermissions(BaseModel):
    can_edit_meet: bool = Field(serialization_alias="canEditMeet")
    can_delete_participants: bool = Field(
        serialization_alias="canDeleteParticipants"
    )
    can_edit_settings: bool = Field(serialization_alias="canEditSettings")
    can_vote: bool = Field(serialization_alias="canVote")
    can_observe: bool = Field(serialization_alias="canObserve")
    can_set_final: bool = Field(serialization_alias="canSetFinal")
    is_observer: bool = Field(serialization_alias="isObserver")


class MeetSettingsUpdate(BaseModel):
    anyone_can_edit: bool = Field(alias="anyoneCanEdit")
    anyone_can_delete_participants: bool = Field(
        alias="anyoneCanDeleteParticipants"
    )
    require_login_to_vote: bool = Field(alias="requireLoginToVote")
    anyone_can_set_final: bool | None = Field(
        None, alias="anyoneCanSetFinal"
    )

    model_config = ConfigDict(populate_by_name=True)


class MeetFinalUpdate(BaseModel):
    slots: list[list[str]]


class UserMeetingItem(BaseModel):
    hash: UUID
    name: str
    description: str | None = None
    duration: str | None = None
    link: str | None = None
    role: Literal["owner", "participant", "observer", "invited"]
    data_range: list[list[str]] = Field(serialization_alias="dataRange")
    has_final: bool = Field(False, serialization_alias="hasFinal")
    participant_names: list[str] = Field(
        default_factory=list, serialization_alias="participantNames"
    )
    participant_count: int = Field(0, serialization_alias="participantCount")

    model_config = ConfigDict(populate_by_name=True)


class Meet(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=400)
    link: str | None = Field(None, max_length=128)
    duration: str | None = None
    dataRange: list[list[str]] | None = Field(
        None,
        alias="data_range",
        serialization_alias="dataRange",
    )
    invited_user_ids: list[UUID] | None = Field(
        None, alias="invitedUserIds"
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class MeetCreate(Meet):
    pass


class MeetResponse(Meet):
    hash: UUID = Field(validation_alias="id")
    slots: list[SlotsUser] = []
    is_creator: bool | None = Field(None, serialization_alias="isCreator")
    is_creator_auth: bool | None = Field(
        None, serialization_alias="isCreatorAuth"
    )
    anyone_can_edit: bool = Field(True, serialization_alias="anyoneCanEdit")
    anyone_can_delete_participants: bool = Field(
        True, serialization_alias="anyoneCanDeleteParticipants"
    )
    require_login_to_vote: bool = Field(
        False, serialization_alias="requireLoginToVote"
    )
    anyone_can_set_final: bool = Field(
        False, serialization_alias="anyoneCanSetFinal"
    )
    final_slot: list[list[str]] | None = Field(
        None, serialization_alias="finalSlot"
    )
    organizer_name: str | None = Field(
        None, serialization_alias="organizerName"
    )
    observers: list[ObserverUser] = []
    permissions: MeetPermissions | None = None

    @field_validator("slots", mode="before")
    @classmethod
    def validate_slots(cls, slots_db):
        return [
            SlotsUser(
                name=slot["name"],
                userId=slot.get("user_id"),
                slots=slot["slots"],
                is_auth=slot.get("user_id") is not None,
            )
            for slot in slots_db or []
        ]
