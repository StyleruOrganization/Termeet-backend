from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3.client import S3Client

from backend.src.auth.utils import REFRESH_TOKEN_COOKIE
from backend.src.schemas import ErrorResponse
from backend.src.dependencies import get_async_session, get_s3_client
from backend.src.auth.dependencies import get_required_active_user
from backend.src.users.schemas import (
    CalendarMonthResponse,
    UserSchema,
    UserSearchItem,
    UserSettingsUpdate,
)
from backend.src.users.services import Service as UsersService
from backend.src.meetings.schemas import UserMeetingItem
from backend.src.meetings.services import Service as MeetingsService


router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserSchema,
    summary="Информация о текущем пользователе",
    description="Получает юзера из access-токена, проверяет его в БД и \
        возвращает его данные",
    responses={
        403: {
            "description": "Пользователь заблокирован",
            "model": ErrorResponse
        },
        401: {
            "description": "Срок действия access_токена истек / \
                Не правильный тип токена",
            "model": ErrorResponse
        },
        404: {
            "description": "Объект не найден",
            "model": ErrorResponse
        },
    }
)
async def auth_user(
    user: UserSchema = Depends(get_required_active_user),
):
    return user


@router.patch(
    "/me",
    response_model=UserSchema,
    summary="Обновить настройки профиля",
)
async def update_me(
    payload: UserSettingsUpdate,
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = UsersService(session)
    return await service.update_settings(user, payload)


@router.get(
    "/search",
    response_model=list[UserSearchItem],
    summary="Найти пользователей Termeet",
)
async def search_users(
    q: str = Query("", min_length=0, max_length=64),
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = UsersService(session)
    return await service.search_users(q, user)


@router.delete(
    "/me",
    summary="Удалить аккаунт текущего пользователя",
)
async def delete_me(
    response: Response,
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = UsersService(session)
    await service.delete_account(user)
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        path="/",
    )
    return {"detail": "Account deleted"}


@router.get(
    "/me/calendar",
    response_model=CalendarMonthResponse,
    summary="События Яндекс Календаря текущего пользователя",
)
async def my_calendar(
    start: str = Query(..., description="ISO начало окна"),
    end: str = Query(..., description="ISO конец окна"),
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    from datetime import datetime

    def parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    service = UsersService(session)
    return await service.list_calendar(user, parse(start), parse(end))


@router.get(
    "/me/meetings",
    response_model=list[UserMeetingItem],
    summary="Встречи текущего пользователя",
)
async def my_meetings(
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = MeetingsService(session)
    return await service.list_user_meetings(user)


@router.post(
    "/me/avatar",
    response_model=UserSchema,
    summary="Загрузить фото профиля",
)
async def upload_my_avatar(
    file: UploadFile = File(...),
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
    s3_client: S3Client = Depends(get_s3_client),
):
    service = UsersService(session)
    return await service.set_avatar(user, file, s3_client)


@router.get(
    "/{user_id}/avatar",
    summary="Фото пользователя",
)
async def user_avatar(
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    s3_client: S3Client = Depends(get_s3_client),
):
    service = UsersService(session)
    return await service.get_avatar(user_id, s3_client)
