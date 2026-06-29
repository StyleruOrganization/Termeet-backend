from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

class Repository(ABC):
    def __init__(self, session: AsyncSession):
        self.session = session
