from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


_API = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    serialize_by_alias=True,
)


class TeamMember(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    has_avatar: bool = False

    model_config = _API


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field("", max_length=400)
    member_ids: list[UUID] = Field(
        default_factory=list,
        validation_alias=AliasChoices("member_ids", "memberIds"),
        serialization_alias="memberIds",
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("member_ids")
    @classmethod
    def limit_members(cls, value):
        if value is not None and len(value) > 100:
            raise ValueError("В команде максимум 100 человек")
        return value or []


class TeamUpdate(TeamCreate):
    pass


class TeamResponse(BaseModel):
    id: int
    name: str
    description: str = ""
    has_photo: bool = Field(False, serialization_alias="hasPhoto")
    is_owner: bool = Field(False, serialization_alias="isOwner")
    members: list[TeamMember] = Field(default_factory=list)

    model_config = _API
