from uuid import UUID

from jwt.exceptions import InvalidTokenError
from starlette import status
from fastapi import Depends, HTTPException, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.auth.infrastructure import Infrastructure
from backend.src.auth.utils import (
    decode_jwt,
    TOKEN_TYPE_FIELD,
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    REFRESH_TOKEN_COOKIE
)
from backend.src.dependencies import get_async_session
from backend.src.auth.schemas import UserSchema


# Подумай насчет OAuth2PasswordBearer
http_bearer = HTTPBearer()


async def _get_current_access_token_payload(
        credentials: HTTPAuthorizationCredentials = Depends(http_bearer)
):
    token: str = credentials.credentials

    try:
        payload = await decode_jwt(token=token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token error"
        )

    return payload


async def _get_current_refresh_token_payload(
        refresh_token: str = Cookie(alias=REFRESH_TOKEN_COOKIE)
) -> dict:
    try:
        payload = await decode_jwt(token=refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token error"
        )

    return payload


async def _get_current_auth_user(
        payload: dict = Depends(_get_current_access_token_payload),
        session: AsyncSession = Depends(get_async_session)
):
    token_type = payload.get(TOKEN_TYPE_FIELD)
    if token_type != ACCESS_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token type"
        )
    user_id: UUID | None = UUID(payload.get("sub"))
    # От сюда можно доставать и другое, чтобы не доставать это из БД
    repository = Infrastructure(session)

    if user := (await repository.check_user_in_db(user_id)):
        user: UserSchema = UserSchema.model_validate(user)
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="token invalid (user not found)"
    )


async def get_current_auth_user_for_refresh(
        payload: dict = Depends(_get_current_refresh_token_payload),
        session: AsyncSession = Depends(get_async_session)
):
    token_type = payload.get(TOKEN_TYPE_FIELD)
    if token_type != REFRESH_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token type"
        )
    user_id: UUID | None = UUID(payload.get("sub"))
    # От сюда можно доставать и другое, чтобы не доставать это из БД
    repository = Infrastructure(session)

    if user := (await repository.check_user_in_db(user_id)):
        user: UserSchema = UserSchema.model_validate(user)
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="token invalid (user not found)"
    )


async def get_current_active_user(
        user: UserSchema = Depends(_get_current_auth_user)
):
    if user.is_active:
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="user inactive"
    )
