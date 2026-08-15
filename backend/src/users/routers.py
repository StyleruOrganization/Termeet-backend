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
    BotMeetCreateIn,
    BotMeetFinalIn,
    BotMeetFromTemplateIn,
    BotMeetFromTemplateOut,
    BotContextOut,
    BotMeetPushIn,
    BotMeetPushOut,
    BotMeetStatusOut,
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
from backend.src.meetings.schemas import MeetCreate, MeetResponse, UserMeetingItem
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


@bot_router.post(
    "/telegram/meet/create",
    response_model=MeetResponse,
    summary="Создать встречу от привязанного Telegram",
)
async def bot_create_meeting(
    payload: BotMeetCreateIn,
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    users = UsersService(session)
    user = await users.user_by_telegram_id(payload.telegram_user_id)
    meeting = MeetCreate(
        name=payload.name,
        data_range=payload.data_range,
        description=payload.description,
        duration=payload.duration,
        link=payload.link,
    )
    meetings = MeetingsService(session)
    return await meetings.create_meeting(meeting, user)


@bot_router.post(
    "/telegram/meet/push",
    response_model=BotMeetPushOut,
    summary="Пуш организатора участникам с Telegram",
)
async def bot_push_meeting(
    payload: BotMeetPushIn,
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    users = UsersService(session)
    user = await users.user_by_telegram_id(payload.telegram_user_id)
    meetings = MeetingsService(session)
    return await meetings.push_telegram(
        payload.hash,
        user,
        payload.note,
        only_pending=payload.only_pending,
    )


@bot_router.get(
    "/telegram/meet/{meet_hash}",
    response_model=BotMeetStatusOut,
    summary="Карточка встречи для бота",
)
async def bot_meeting_status(
    meet_hash: UUID,
    telegram_user_id: int = Query(...),
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    users = UsersService(session)
    user = await users.user_by_telegram_id(telegram_user_id)
    meetings = MeetingsService(session)
    return await meetings.bot_status(meet_hash, user)


@bot_router.post(
    "/telegram/meet/final",
    response_model=MeetResponse,
    summary="Назначить итог из бота",
)
async def bot_set_final(
    payload: BotMeetFinalIn,
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    users = UsersService(session)
    user = await users.user_by_telegram_id(payload.telegram_user_id)
    meetings = MeetingsService(session)
    return await meetings.bot_set_final(payload.hash, user, payload.slots)


@bot_router.get(
    "/telegram/context",
    response_model=BotContextOut,
    summary="Шаблоны и команды для бота",
)
async def bot_telegram_context(
    telegram_user_id: int = Query(...),
    telegram_username: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    users = UsersService(session)
    user = await users.user_by_telegram_id(
        telegram_user_id, telegram_username
    )
    from backend.src.teams.services import Service as TeamService

    teams = await TeamService(session).list_teams(user)
    return {
        "timezone": user.timezone,
        "templates": user.bot_templates or [],
        "teams": [
            {"id": item.id, "slug": item.slug, "name": item.name}
            for item in teams
            if item.slug
        ],
    }


@bot_router.post(
    "/telegram/meet/from-template",
    response_model=BotMeetFromTemplateOut,
    summary="Создать встречу из шаблона бота",
)
async def bot_meet_from_template(
    payload: BotMeetFromTemplateIn,
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_bot_secret),
):
    users = UsersService(session)
    user = await users.user_by_telegram_id(
        payload.telegram_user_id, payload.telegram_username
    )
    meetings = MeetingsService(session)
    from backend.src.bot_templates.apply import create_from_template

    created, missing = await create_from_template(
        meetings,
        user,
        payload.slug,
        payload.tokens,
        [item.model_dump() for item in payload.mentions],
        payload.note,
    )
    return {
        "hash": created.hash,
        "name": created.name,
        "has_final": bool(created.final_slot),
        "missing": missing,
    }
