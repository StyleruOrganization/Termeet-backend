from uuid import UUID
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select
from fastapi import HTTPException
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_403_FORBIDDEN,
    HTTP_401_UNAUTHORIZED,
)

from backend.src.meetings.repositories import Repository
from backend.src.meetings.models import Meetings
from backend.src.users.schemas import UserSchema
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
            Meetings.emails,
        ).where(Meetings.id == id)

        result: Result = await self.session.execute(query)

        record: Optional[Meetings] = result.one_or_none()

        if not record:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Meeting not found"
            )

        return record

    async def create_meeting(
        self, meeting: dict, user: UserSchema | None
    ) -> Optional[Meetings]:

        object: Meetings = Meetings(
            name=meeting["name"],
            description=meeting["description"],
            link=meeting["link"],
            duration=meeting["duration"],
            data_range=meeting["dataRange"],
            slots=[],
        )

        if user:
            if user := await self.session.get(Users, user.id):
                object.owner = user
            else:
                raise HTTPException(
                    status_code=HTTP_404_NOT_FOUND, detail="User not found"
                )       

        self.session.add(object)
        await self.session.flush()
        return object

    async def edit_meeting(
        self, id: UUID, meeting: dict, user: UserSchema | None
    ) -> Optional[Meetings]:

        record: Meetings | None = await self.session.get(Meetings, id)

        if not record:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Meeting not found"
            )

        if not user:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to edit this meeting",
            )

        if record.owner_id != user.id:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="You are not the owner of this meeting",
            )

        record.name = meeting["name"]
        record.description = meeting["description"]
        record.link = meeting["link"]
        record.duration = meeting["duration"]
        record.data_range = meeting["dataRange"]

        await self.session.flush()
        return record

    async def add_slots(
        self, id: UUID, name: str, slots: list, user: UserSchema | None
    ):
        record: Meetings | None = await self.session.get(Meetings, id)

        if not record:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Meeting not found"
            )

        if user:
            if user := await self.session.get(Users, user.id):
                record.participants.append(user)  # Здесь проблемы с асинхронностью - решить!
            else:
                raise HTTPException(
                    status_code=HTTP_404_NOT_FOUND, detail="User not found"
                )

        current_slots = record.slots.copy() if record.slots else []
        
        # Теперь же в слоты будем доавблять id пользователя, который выбрал эти слоты
        current_slots.append({name: slots, "user_id": user.id if user else None})

        record.slots = current_slots

        self.session.add(record)
        await self.session.flush()

    async def edit_slots(
        self, id: UUID, name: str, slots: list, user: UserSchema | None
    ):
        record: Meetings | None = await self.session.get(Meetings, id)

        if not record:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Meeting not found"
            )

        if not user:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to edit slots of this meeting",
            )
        elif user := (await self.session.get(Users, user.id)):
                if user not in record.participants:
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail="You are not a participant of this meeting",
                    )
        else:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="User not found"
            )

        current_slots = record.slots.copy() if record.slots else []

        for slot in current_slots:
            if slot.get("user_id") == user.id:
                slot = {name: slots, "user_id": user.id}
                break
        else:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Slots for this user not found in this meeting",
            )

        record.slots = current_slots

        await self.session.flush()