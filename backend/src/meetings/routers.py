from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.schemas import ErrorResponse
from backend.src.dependencies import get_async_session
from backend.src.auth.dependencies import get_current_active_user
from backend.src.users.schemas import UserSchema
from .schemas import MeetCreate, MeetResponse, SlotsUser
from .services import Service


router = APIRouter(prefix="/meet", tags=["Meet"])


@router.get(
    "/{hash}",
    response_model=MeetResponse,
    summary="Получить всю информацию о встрече",
    description="Возвращает слоты встречи для выбора, \
                а также уже выбранные участниками",
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
async def get_meeting(
    hash: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
) -> MeetResponse:
    service = Service(session)
    return await service.get_meeting(hash, user)


@router.post(
    "/create",
    response_model=MeetResponse,
    response_model_exclude_none=True,
    summary="Создать встречу",
    description="Создает слоты для встречи по определенным дням \
                и промежутку времени",
    status_code=201,
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
async def create_meeting(
    meeting: MeetCreate,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
) -> MeetResponse:
    service = Service(session)
    return await service.create_meeting(meeting, user)


@router.patch(
    "/{hash}",
    summary="Редактировать встречу",
    description="Отправляет полное описание встречи, \
        то есть измененные и не измененные",
    responses={
        403: {
            "description": "Пользователь заблокирован / \
                Пользователь не является создателем встречи",
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
async def edit_meeting(
    hash: UUID,
    meeting: MeetCreate,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
):
    service = Service(session)
    return await service.edit_meeting(hash, meeting, user)


@router.patch(
    "/{hash}/slots",
    summary="Отправить слоты, выбранные пользователем",
    description="Отправляет слоты встречи, которые выбрал \
                пользователь",
    responses={
        403: {
            "description": "Пользователь заблокирован / \
                Пользователь уже добавил слоты для этой встречи / \
                Слоты с таким никнеймом пользователя уже существуют",
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
async def add_slots(
    hash: UUID,
    slots: SlotsUser,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
):
    service = Service(session)
    return await service.add_slots(hash, slots, user)


@router.patch(
    "/{hash}/slots/edit",
    summary="Отредактировать слоты, выбранные пользователем",
    description="Отправляет отредактированные слоты встречи, \
                которые выбрал пользователь",
    responses={
        403: {
            "description": "Пользователь заблокирован / \
                Пользователь не является участником встречи / \
                Слоты для этого пользователя не найдены",
            "model": ErrorResponse
        },
        401: {
            "description": "Срок действия access_токена истек / \
                Не правильный тип токена / \
                Пользователь должен быть аутентифицирован, \
                чтобы редактировать слоты",
            "model": ErrorResponse
        },
        404: {
            "description": "Объект не найден",
            "model": ErrorResponse
        },
    }
)
async def edit_slots(
    hash: UUID,
    slots: SlotsUser,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
):
    service = Service(session)
    return await service.edit_slots(hash, slots, user)


@router.delete(
    "/{hash}/slots/{username}",
    summary="Удалить слоты, выбранные пользователем",
    description="Удаляет слоты встречи, которые выбрал \
                пользователь",
    responses={
        403: {
            "description": "Пользователь заблокирован / \
                Пользователь не является создателем встречи",
            "model": ErrorResponse
        },
        401: {
            "description": "Срок действия access_токена истек / \
                Не правильный тип токена",
            "model": ErrorResponse
        },
        404: {
            "description": "Объект не найден / \
            Слоты для этого никнейма не найдены",
            "model": ErrorResponse
        },
    }
)
async def delete_slots(
    hash: UUID,
    username: str,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
):
    service = Service(session)
    return await service.delete_slots_of_user(hash, username, user)
