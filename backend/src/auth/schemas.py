import re

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator

from backend.src.auth.utils import hash_password

_STRONG_PASSWORD = re.compile(
    r"^(?=.*[a-zа-яё])(?=.*[A-ZА-ЯЁ])(?=.*\d).{8,128}$"
)


def _require_strong_password(value: str) -> str:
    if not _STRONG_PASSWORD.fullmatch(value or ""):
        raise ValueError(
            "Password must be 8+ characters with upper, lower and a digit"
        )
    return value


class Code(BaseModel):
    code: str = Field(..., min_length=1, max_length=128)
    state: str | None = None


class YandexTokenLogin(BaseModel):
    access_token: str = Field(..., min_length=8, max_length=4096)
    expires_in: int | None = None
    state: str | None = None


class YandexClientPublic(BaseModel):
    client_id: str
    scope: str


class Email(BaseModel):
    email: EmailStr = Field(..., max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class Password(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _require_strong_password(value)


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 0
    scope: str | None = None

    model_config = ConfigDict(extra="ignore")


class YandexUserData(BaseModel):
    id: str
    login: str = ""
    client_id: str = ""
    display_name: str = ""
    real_name: str = ""
    first_name: str = ""
    last_name: str = ""
    sex: str = ""
    default_email: str
    emails: list = Field(default_factory=list)
    psuid: str = ""

    model_config = ConfigDict(extra="ignore")


class RegisterUserData(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)
    email: EmailStr = Field(..., max_length=128)
    password: str = Field(..., min_length=8, max_length=128)
    do_verify_email: bool = True

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _require_strong_password(value)

    @field_validator("email", "first_name", "last_name", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


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
            email=str(data.email).strip().lower(),
            password_hash=await hash_password(data.password),
            provider="DEFAULT",
        )


class LoginUserData(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class TokenInfo(BaseModel):
    access_token: str
    token_type: str = "Bearer"
