from pydantic import BaseModel, ConfigDict, Field, EmailStr

from backend.src.auth.utils import hash_password


class Code(BaseModel):
    code: str = Field(..., min_length=1, max_length=128)


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


class RegisterUserData(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)
    email: EmailStr = Field(..., max_length=128)
    password: str = Field(..., min_length=6, max_length=128)
    do_verify_email: bool


class UserData(BaseModel):
    first_name: str
    last_name: str
    email: str
    additional_emails: list[str] | None = None

    password_hash: bytes | None = None

    provider: str | None = None
    provider_user_id: str | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_yandex(cls, data: YandexUserData) -> "UserData":
        return cls(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.default_email,
            additional_emails=data.emails,
            provider="YANDEX",
            provider_user_id=data.id,
        )

    @classmethod
    async def from_register(cls, data: RegisterUserData) -> "UserData":
        return cls(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            password_hash=await hash_password(data.password),
            provider="DEFAULT",
        )


class LoginUserData(BaseModel):
    email: str
    password: str


class TokenInfo(BaseModel):
    access_token: str
    token_type: str = "Bearer"
