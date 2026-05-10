from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.feedback.models import Feedback


class Repository(ABC):
    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def add_feedback(self, feedback: Feedback) -> Feedback:
        pass
