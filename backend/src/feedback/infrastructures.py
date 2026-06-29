from typing import TYPE_CHECKING

from sqlalchemy import select
from fastapi import HTTPException, status

from backend.src.feedback.repositories import Repository
from backend.src.feedback.models import Feedback

if TYPE_CHECKING:
    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession, AsyncResult
    from backend.src.feedback.schemas import Feedback as FeedbackSchema
    from backend.src.users.schemas import UserSchema


class Infrastructure(Repository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def add_feedback(
        self, feedback: FeedbackSchema, user: UserSchema | None
    ) -> Feedback:
        record = Feedback(
            **feedback.model_dump(
                include={
                    "id",
                    "type",
                    "communication_channel",
                    "contact",
                    "message",
                }
            )
        )

        if user:
            record.user_id = user.id

        self.session.add(record)
        await self.session.flush()
        return record

    async def get_all_feedbacks(self) -> list[Feedback]:
        query: Select = select(Feedback)
        result: AsyncResult = await self.session.scalars(query)
        feedbacks: list[Feedback] = result.all()

        if feedbacks == []:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedbacks not found",
            )

        return feedbacks
