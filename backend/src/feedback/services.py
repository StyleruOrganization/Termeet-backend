from typing import TYPE_CHECKING
from uuid import uuid4
from pathlib import Path

from fastapi import UploadFile

from backend.src.feedback.infrastructures import Infrastructure
from backend.src.feedback.schemas import Feedback as FeedbackSchema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.feedback.models import Feedback


class Service:
    def __init__(self, session: AsyncSession = None):
        self.repository = Infrastructure(session)

    async def _save_photos(self, id, photos: list[UploadFile] | None):
        for number, photo in enumerate(photos):

            file_path = (
                Path("feedback_images") / f"{id}" / f"{id}_{number}.jpg"
            )

            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(await photo.read())

    async def add_feedback(
        self, feedback: FeedbackSchema, photos: list[UploadFile] | None = None
    ) -> FeedbackSchema:
        feedback.id = uuid4()

        if photos:
            await self._save_photos(feedback.id, photos)

        record: Feedback = await self.repository.add_feedback(feedback)
        feedback: FeedbackSchema = FeedbackSchema.model_validate(record)
        return feedback
