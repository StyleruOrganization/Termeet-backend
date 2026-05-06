from uuid import UUID

from jwt.exceptions import InvalidTokenError
from starlette import status
from fastapi import Depends, Form, HTTPException, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.auth.schemas import LoginUserData
from backend.src.auth.infrastructure import Infrastructure
from backend.src.auth.utils import (
    decode_jwt,
    validate_password,
    TOKEN_TYPE_FIELD,
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    REFRESH_TOKEN_COOKIE,
    VERIFICATION_TOKEN_TYPE,
)
from backend.src.dependencies import get_async_session
from backend.src.users.schemas import UserSchema


# Подумай насчет OAuth2PasswordBearer
http_bearer = HTTPBearer(auto_error=False)


async def _get_current_access_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
):
    if not credentials:
        return None

    token: str = credentials.credentials

    try:
        payload = await decode_jwt(token=token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token error (access token is expired)",
        )

    return payload


async def _get_current_refresh_token_payload(
    refresh_token: str = Cookie(alias=REFRESH_TOKEN_COOKIE),
) -> dict:
    try:
        payload = await decode_jwt(token=refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token error (refresh token is expired)",
        )

    return payload


async def _get_current_validation_token_payload(
        validation_token: str,
):
    try:
        payload = await decode_jwt(token=validation_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token error (validation token is expired)",
        )

    return payload

async def validate_token_type(payload: dict, token_type: str):
    current_token_type = payload.get(TOKEN_TYPE_FIELD)
    if current_token_type != token_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token type",
        )


async def get_user_by_token_sub(payload: dict, session: AsyncSession):
    user_id: UUID | None = UUID(payload.get("sub"))

    repository = Infrastructure(session)

    if user := (await repository.check_user_in_db_by_id(user_id)):
        # Сохраняю объект в словаре сессии, чтобы не делать повторный запрос😎
        session.info.setdefault("user_cache", {})[user_id] = user
        user: UserSchema = UserSchema.model_validate(user)
        return user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found",
    )


# Фабрика зависимостей😎
def get_auth_user_from_token_of_type(token_type: str):
    if token_type == ACCESS_TOKEN_TYPE:
        current_function_of_token_payload = _get_current_access_token_payload
    elif token_type == REFRESH_TOKEN_TYPE:
        current_function_of_token_payload = _get_current_refresh_token_payload
    else:
        current_function_of_token_payload = _get_current_validation_token_payload

    async def get_auth_user_from_token(
        payload: dict | None = Depends(current_function_of_token_payload),
        session: AsyncSession = Depends(get_async_session),
    ):
        if not payload:
            return None

        await validate_token_type(payload, token_type)
        return await get_user_by_token_sub(payload, session)

    return get_auth_user_from_token


_get_current_auth_user_from_access = get_auth_user_from_token_of_type(
    ACCESS_TOKEN_TYPE
)


get_current_auth_user_from_refresh = get_auth_user_from_token_of_type(
    REFRESH_TOKEN_TYPE
)

get_current_auth_user_from_validation = get_auth_user_from_token_of_type(
    VERIFICATION_TOKEN_TYPE
)


async def get_current_active_user(
    user: UserSchema | None = Depends(_get_current_auth_user_from_access),
):
    if not user:
        return None

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user inactive"
        )

    return user


async def validate_login_user(
    user_data: LoginUserData,
    session: AsyncSession = Depends(get_async_session),
):
    repository = Infrastructure(session)

    if not (
        user := (await repository.check_user_in_db_by_email(user_data.email))
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )

    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )

    if not (await validate_password(user_data.password, user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user inactive"
        )

    user: UserSchema = UserSchema.model_validate(user)

    return user
