from pydantic import BaseModel


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


class RegisterUserData(BaseModel):
    first_name: str
    last_name: str
    default_email: str
    password: str


class LoginUserData(BaseModel):
    email: str
    password: str


class TokenInfo(BaseModel):
    access_token: str
    token_type: str = "Bearer"
