from typing import TYPE_CHECKING
from uuid import uuid4
from pathlib import Path

from fastapi import HTTPException, UploadFile
import aio_pika

from backend.src.config import config
from backend.src.feedback.infrastructures import Infrastructure
from backend.src.feedback.schemas import Feedback as FeedbackSchema

if TYPE_CHECKING:
    from fastapi import BackgroundTasks
    from types_aiobotocore_s3.client import S3Client
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.broker import RabbitMQClient
    from backend.src.users.schemas import UserSchema
    from backend.src.feedback.schemas import Feedback


class Service:
    def __init__(
        self,
        session: AsyncSession | None = None,
        background_tasks: BackgroundTasks | None = None,
        rabbit: RabbitMQClient | None = None,
        s3_client: S3Client | None = None,
    ):
        self.repository = Infrastructure(session)
        self.background_tasks = background_tasks
        self.rabbit = rabbit
        self.s3_client = s3_client

    async def _save_photos(self, id, photos: list[UploadFile] | None):
        for number, photo in enumerate(photos):

            file_path = (
                Path("feedback_images") / f"{id}" / f"{id}_{number}.jpg"
            )

            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(await photo.read())

    async def _sent_to_rabbit(self, feedback: FeedbackSchema):

        message: aio_pika.Message = aio_pika.Message(
            body=feedback.model_dump_json().encode(),
            content_type="application/json",
        )

        await self.rabbit.publish("feedback_queue", message)

    async def add_feedback(
        self,
        feedback: FeedbackSchema,
        photos: list[UploadFile] | None,
        user: UserSchema | None,
    ) -> FeedbackSchema:
        feedback.id = uuid4()

        if photos:
            feedback.count_photos = len(photos)

        for number, photo in enumerate(photos):
            try:
                await self.s3_client.upload_fileobj(
                    Fileobj=photo.file,
                    Bucket=config.s3.BUCKET_NAME,
                    Key=f"{feedback.id}/{feedback.id}_{number}.jpg",
                    ExtraArgs={"ContentType": photo.content_type},
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        self.background_tasks.add_task(self._sent_to_rabbit, feedback)
        if photos:
            self.background_tasks.add_task(
                self._save_photos, feedback.id, photos
            )

        record: Feedback = await self.repository.add_feedback(feedback, user)

        feedback: FeedbackSchema = FeedbackSchema.model_validate(record)
        return feedback

    async def get_all_feedbacks(self) -> list[FeedbackSchema]:

        records: list[Feedback] = await self.repository.get_all_feedbacks()

        feedbacks: list[FeedbackSchema] = [
            FeedbackSchema.model_validate(f) for f in records
        ]

        return feedbacks
