from fastapi import APIRouter, Depends, UploadFile, BackgroundTasks, File
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3.client import S3Client

from backend.src.schemas import ErrorResponse
from backend.src.broker import RabbitMQClient
from backend.src.dependencies import (
    get_async_session,
    get_rabbit,
    get_s3_client,
)
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
    photos: list[UploadFile] | None = File(default=None),
    user: UserSchema | None = Depends(get_current_active_user),
    feedback: Feedback = Depends(feedback_as_form),
    session: AsyncSession = Depends(get_async_session),
    rabbit: RabbitMQClient = Depends(get_rabbit),
    s3_client: S3Client = Depends(get_s3_client),
):
    service = Service(session, background_tasks, rabbit, s3_client)
    return await service.add_feedback(feedback, photos, user)


@router.get(
    "/get-all",
    summary="Получить все отзывы",
    description="Получает все отзывы",
    response_model=list[Feedback],
    responses={
        404: {
            "description": "Объект не найден",
            "model": ErrorResponse,
        },
    },
)
async def get_all_feedbacks(
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session)
    return await service.get_all_feedbacks()
