from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Code(BaseModel):
    code: str


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class YandexUserData(BaseModel):
    id: str
    login: str
    client_id: str
    display_name: str
    real_name: str
    first_name: str
    last_name: str
    sex: str
    default_email: str
    emails: list
    psuid: str


class UserSchema(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    is_active: bool
    email: str
    additional_emails: Optional[list]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class TokenInfo(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
