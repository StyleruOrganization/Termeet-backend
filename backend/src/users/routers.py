from uuid import UUID
import hmac

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3.client import S3Client
from starlette import status

from backend.src.auth.utils import REFRESH_TOKEN_COOKIE
from backend.src.config import config
from backend.src.schemas import ErrorResponse
from backend.src.dependencies import get_async_session, get_s3_client
from backend.src.auth.dependencies import get_required_active_user
from backend.src.users.schemas import (
    CalendarEventCreate,
    CalendarEventItem,
    CalendarMonthResponse,
    TelegramConfirmIn,
    TelegramConfirmOut,
    TelegramLinkResponse,
    TelegramUnlinkIn,
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


@router.post(
    "/me/calendar",
    response_model=CalendarEventItem,
    summary="Создать событие в Яндекс Календаре",
)
async def create_calendar_event(
    payload: CalendarEventCreate,
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = UsersService(session)
    return await service.create_calendar_event(user, payload)


@router.delete(
    "/me/calendar",
    summary="Удалить событие из Яндекс Календаря",
)
async def delete_calendar_event(
    href: str = Query(..., min_length=1),
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = UsersService(session)
    await service.delete_calendar_event(user, href)
    return {"detail": "Event deleted"}


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
    "/me/telegram/link",
    response_model=TelegramLinkResponse,
    summary="Ссылка, чтобы привязать Telegram к аккаунту",
)
async def start_telegram_link(
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = UsersService(session)
    return await service.start_telegram_link(user)


@router.post(
    "/me/telegram/unlink",
    response_model=UserSchema,
    summary="Отвязать Telegram от аккаунта",
)
async def unlink_telegram(
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = UsersService(session)
    return await service.unlink_telegram_for_user(user)


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


def require_bot_secret(
    x_telegram_bot_secret: str | None = Header(default=None),
):
    expected = config.telegram_bot.SECRET or ""
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot secret is not configured",
        )
    given = (x_telegram_bot_secret or "").encode("utf-8")
    expected_b = expected.encode("utf-8")
    if not hmac.compare_digest(given, expected_b):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot secret",
        )


bot_router = APIRouter(prefix="/bot", tags=["Bot"])


@bot_router.post(
    "/telegram/confirm",
    response_model=TelegramConfirmOut,
    summary="Подтвердить привязку Telegram (только бот)",
)
async def bot_confirm_telegram(
    payload: TelegramConfirmIn,
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    service = UsersService(session)
    return await service.confirm_telegram_link(payload)


@bot_router.post(
    "/telegram/unlink",
    summary="Отвязать Telegram по id (только бот)",
)
async def bot_unlink_telegram(
    payload: TelegramUnlinkIn,
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    service = UsersService(session)
    await service.unlink_telegram_by_id(payload.telegram_user_id)
    return {"detail": "Telegram unlinked"}


@bot_router.get(
    "/telegram/meetings",
    response_model=list[UserMeetingItem],
    summary="Встречи пользователя по Telegram id (только бот)",
)
async def bot_telegram_meetings(
    telegram_user_id: int = Query(...),
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    users = UsersService(session)
    user = await users.user_by_telegram_id(telegram_user_id)
    meetings = MeetingsService(session)
    return await meetings.list_user_meetings(user)
