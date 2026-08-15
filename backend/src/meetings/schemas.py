from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


def _json_names(snake: str, camel: str) -> AliasChoices:
    # snake первым: ORM читает колонку, camel — JSON с фронта.
    return AliasChoices(snake, camel)


_API = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    serialize_by_alias=True,
)


class SlotsUser(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    user_id: UUID | None = Field(None, alias="userId")
    slots: list[list[str]]
    is_auth: bool = Field(False, alias="isAuth")

    model_config = _API


class ObserverUser(BaseModel):
    name: str
    user_id: str | None = Field(None, alias="userId")

    model_config = _API


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

    model_config = ConfigDict(serialize_by_alias=True)


class MeetSettingsUpdate(BaseModel):
    anyone_can_edit: bool = Field(
        validation_alias=_json_names("anyone_can_edit", "anyoneCanEdit"),
        serialization_alias="anyoneCanEdit",
    )
    anyone_can_delete_participants: bool = Field(
        validation_alias=_json_names(
            "anyone_can_delete_participants", "anyoneCanDeleteParticipants"
        ),
        serialization_alias="anyoneCanDeleteParticipants",
    )
    require_login_to_vote: bool = Field(
        validation_alias=_json_names(
            "require_login_to_vote", "requireLoginToVote"
        ),
        serialization_alias="requireLoginToVote",
    )
    anyone_can_set_final: bool | None = Field(
        None,
        validation_alias=_json_names(
            "anyone_can_set_final", "anyoneCanSetFinal"
        ),
        serialization_alias="anyoneCanSetFinal",
    )

    model_config = ConfigDict(populate_by_name=True)


class MeetFinalUpdate(BaseModel):
    slots: list[list[str]]


class CalendarConflict(BaseModel):
    name: str
    titles: list[str] = Field(default_factory=list)

    model_config = _API


class CalendarSyncInfo(BaseModel):
    synced: int = 0
    conflicts: list[CalendarConflict] = Field(default_factory=list)

    model_config = _API


class UserMeetingItem(BaseModel):
    hash: UUID
    name: str
    description: str | None = None
    duration: str | None = None
    link: str | None = None
    role: Literal["owner", "participant", "observer", "invited"]
    data_range: list[list[str]] = Field(serialization_alias="dataRange")
    has_final: bool = Field(False, serialization_alias="hasFinal")
    final_slot: list[list[str]] | None = Field(
        None, serialization_alias="finalSlot"
    )
    participant_names: list[str] = Field(
        default_factory=list, serialization_alias="participantNames"
    )
    participant_count: int = Field(0, serialization_alias="participantCount")

    model_config = _API


class Meet(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=400)
    link: str | None = Field(None, max_length=256)
    duration: str | None = None
    data_range: list[list[str]] | None = Field(
        None,
        validation_alias=_json_names("data_range", "dataRange"),
        serialization_alias="dataRange",
    )
    invited_user_ids: list[str] | None = Field(
        None,
        validation_alias=_json_names("invited_user_ids", "invitedUserIds"),
        serialization_alias="invitedUserIds",
    )

    model_config = _API


class MeetCreate(Meet):
    create_telemost: bool = Field(
        False,
        validation_alias=_json_names("create_telemost", "createTelemost"),
        serialization_alias="createTelemost",
    )


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
    calendar_sync: "CalendarSyncInfo | None" = Field(
        None, serialization_alias="calendarSync"
    )

    @field_validator("slots", mode="before")
    @classmethod
    def validate_slots(cls, slots_db):
        result = []
        for slot in slots_db or []:
            if not isinstance(slot, dict) or not slot.get("name"):
                continue
            result.append(
                SlotsUser(
                    name=slot["name"],
                    userId=slot.get("user_id"),
                    slots=slot.get("slots") or [],
                    is_auth=slot.get("user_id") is not None,
                )
            )
        return result
