from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

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
    summary="Создать встречу",
    description="Создает слоты для встречи по определенным дням \
                и промежутку времени",
    status_code=201,
)
async def create_meeting(
    meeting: MeetCreate,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
) -> MeetResponse:
    service = Service(session)
    return await service.create_meeting(meeting, user)


# Это только для зарегистрированных пользователей
@router.patch(
    "/{hash}",
    summary="Редактировать встречу",
    description="Отправляет полное описание встречи, \
        то есть измененные и не измененные",
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
)
async def add_slots(
    hash: UUID,
    slots: SlotsUser,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
):
    service = Service(session)
    return await service.add_slots(hash, slots, user)


# Это только для зарегистрированных пользователей
@router.patch(
    "/{hash}/slots/edit",
    summary="Отредактировать слоты, выбранные пользователем",
    description="Отправляет отредактированные слоты встречи, \
                которые выбрал пользователь",
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
)
async def delete_slots(
    hash: UUID,
    username: str,
    session: AsyncSession = Depends(get_async_session),
    user: UserSchema | None = Depends(get_current_active_user),
):
    service = Service(session)
    return await service.delete_slots_of_user(hash, username, user)
