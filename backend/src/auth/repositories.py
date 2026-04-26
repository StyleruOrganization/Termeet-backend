from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from uuid import UUID
    from backend.src.users.models import Users


class Repository(ABC):
    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def register_user(self, user: dict, provider: str) -> Users:
        pass

    @abstractmethod
    async def yandex_check_user_in_db(self, user: dict) -> Users | None:
        pass

    @abstractmethod
    async def check_user_in_db_by_id(self, id: UUID) -> Users | None:
        pass

    @abstractmethod
    async def check_user_in_db_by_email(self, email: str) -> Users | None:
        pass
