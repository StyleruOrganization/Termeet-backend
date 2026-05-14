from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.schemas import ErrorResponse
from backend.src.dependencies import get_async_session
from backend.src.feedback.schemas import Feedback
from backend.src.feedback.services import Service
from backend.src.feedback.dependencies import feedback_as_form
from backend.src.users.schemas import UserSchema
from backend.src.auth.dependencies import get_current_active_user

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post(
    "/send",
    summary="Отправить отзыв",
    description="Отправляет отзыв",
    response_model=Feedback,
    responses={
        401: {
            "description": "Срок действия токена истек \
                Не правильный тип токена",
            "model": ErrorResponse,
        },
        404: {
            "description": "Объект не найден",
            "model": ErrorResponse,
        },
    },
)
async def send_feedback(
    background_tasks: BackgroundTasks,
    photos: list[UploadFile] | None = None,
    user: UserSchema | None = Depends(get_current_active_user),
    feedback: Feedback = Depends(feedback_as_form),
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session, background_tasks)
    return await service.add_feedback(feedback, photos, user)
