from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


class Repository():
    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def register_user(self, user: dict):
        pass
