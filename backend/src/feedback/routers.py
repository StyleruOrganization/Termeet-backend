from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.dependencies import get_async_session
from backend.src.feedback.schemas import Feedback
from backend.src.feedback.services import Service
from backend.src.feedback.dependencies import feedback_as_form

router = APIRouter(prefix="/feedback", tags=["Feedback"])


# Добавить user-а сюда
@router.post(
    "/send",
    summary="Отправить отзыв",
    description="Отправляет отзыв",
    response_model=Feedback,
)
async def send_feedback(
    photos: list[UploadFile] | None,
    feedback: Feedback = Depends(feedback_as_form),
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session)
    return await service.add_feedback(feedback, photos)
