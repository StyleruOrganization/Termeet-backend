from uuid import UUID
from typing import TYPE_CHECKING
from backend.src.feedback.repositories import Repository
from backend.src.feedback.models import Feedback
from backend.src.users.models import Users

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.feedback.schemas import Feedback as FeedbackSchema
    from backend.src.users.schemas import UserSchema


class Infrastructure(Repository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def add_feedback(
        self, feedback: FeedbackSchema, user: UserSchema | None
    ) -> Feedback:
        record = Feedback(**feedback.model_dump())

        if user:
            record.user_id = user.id

        self.session.add(record)
        await self.session.flush()
        return record
