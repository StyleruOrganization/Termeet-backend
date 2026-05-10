from typing import TYPE_CHECKING
from backend.src.feedback.repositories import Repository
from backend.src.feedback.models import Feedback

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.feedback.schemas import Feedback as FeedbackSchema


class Infrastructure(Repository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def add_feedback(self, feedback: FeedbackSchema) -> Feedback:
        record = Feedback(**feedback.model_dump())
        self.session.add(record)
        await self.session.flush()
        return record
