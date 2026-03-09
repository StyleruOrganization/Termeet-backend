from uuid import UUID
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select
from fastapi import HTTPException

from .repositories import Repository
from .models import Meetings
from backend.src.users.models import Users  # noqa:
from backend.src.teams.models import Teams  # noqa:

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import Select
    from sqlalchemy.engine import Result


# Для незалогинов
class Infrastructure(Repository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_meeting(self, id: UUID) -> Optional[Meetings]:
        query: Select = select(
            Meetings.id,
            Meetings.name,
            Meetings.description,
            Meetings.link,
            Meetings.duration,
            Meetings.data_range,
            Meetings.slots,
            Meetings.emails
            ).where(Meetings.id == id)

        result: Result = await self.session.execute(query)

        record: Optional[Meetings] = result.one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="Meeting not found")

        return record

    async def create_meeting(self, meeting: dict) -> Optional[Meetings]:
        object = Meetings(
            name=meeting["name"],
            description=meeting["description"],
            link=meeting["link"],
            duration=meeting["duration"],
            data_range=meeting["dataRange"],
            slots=[]
        )
        self.session.add(object)
        await self.session.commit()  # Разберись потом, зачем он нужен
        return object

    async def add_slots(self, id: UUID, name: str, slots: list):
        query: Select = select(
            Meetings
            ).where(Meetings.id == id)

        result: Result = await self.session.execute(query)

        # Список из словарей
        record: Optional[Meetings] = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="Meeting not found")

        current_slots = (
            record.slots.copy() if record.slots else []
        )

        # Можно сделать чтобы и в БД по умолчанию пустой список
        current_slots.append({name: slots})

        record.slots = current_slots

        await self.session.commit()
