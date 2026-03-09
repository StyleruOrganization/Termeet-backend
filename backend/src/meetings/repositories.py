from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


class Repository(ABC):
    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def get_meeting(self):
        pass

    @abstractmethod
    async def create_meeting(self):
        pass

    @abstractmethod
    async def add_slots(self):
        pass
