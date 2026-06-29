from uuid import uuid4
from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.src.feedback.models import Feedback
from backend.src.feedback.schemas import Feedback as FeedbackSchema

if TYPE_CHECKING:
    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncResult, AsyncSession


async def test_get_all_feedbacks(session: AsyncSession):
    feedback: FeedbackSchema = FeedbackSchema(
        id=uuid4(),
        type="HELP",
        communication_channel="EMAIL",
        contact="email",
        message="Классное приложение",
    )

    session.add(Feedback(**feedback.model_dump()))
    await session.flush()

    query: Select = select(Feedback)
    result: AsyncResult = await session.scalars(query)
    feedbacks: list[Feedback] = result.all()

    feedback_schemas: list[FeedbackSchema] = [
        FeedbackSchema.model_validate(f) for f in feedbacks
    ]
    print(feedback_schemas)
