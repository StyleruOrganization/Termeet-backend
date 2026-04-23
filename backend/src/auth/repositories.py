from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from uuid import UUID


class Repository(ABC):
    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def register_user(self, user: dict):
        pass

    @abstractmethod
    async def yandex_check_user_in_db(self, user: dict):
        pass

    @abstractmethod
    async def check_user_in_db(self, id: UUID):
        pass
