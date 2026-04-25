from uuid import UUID
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
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
    from sqlalchemy.ext.asyncio import AsyncSession, AsyncResult
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
        query: Select = select(Meetings).options(selectinload(Meetings.participants)).where(Meetings.id == id)

        result: AsyncResult = await self.session.execute(query)

        meeting: Meetings = result.scalar_one_or_none()

        if not meeting:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Meeting not found"
            )

        if user:
            if user := await self.session.get(Users, user.id):
                if user in meeting.participants:
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail="You have already added slots for this meeting",
                    )
                meeting.participants.append(user)
            else:
                raise HTTPException(
                    status_code=HTTP_404_NOT_FOUND, detail="User not found"
                )

        current_slots = meeting.slots.copy() if meeting.slots else []

        # Теперь же в слоты будем добвавлять id пользователя, который выбрал эти слоты
        current_slots.append({name: slots, "user_id": str(user.id) if user else None})

        meeting.slots = current_slots

        self.session.add(meeting)
        await self.session.flush()

    async def edit_slots(
        self, id: UUID, name: str, slots: list, user: UserSchema | None
    ):
        query: Select = select(Meetings).options(selectinload(Meetings.participants)).where(Meetings.id == id)
        result: AsyncResult = await self.session.execute(query)
        meeting: Meetings = result.scalar_one_or_none()

        if not meeting:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Meeting not found"
            )

        if not user:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to edit slots of this meeting",
            )
        elif user := (await self.session.get(Users, user.id)):
                if user not in meeting.participants:
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail="You are not a participant of this meeting",
                    )
        else:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="User not found"
            )

        current_slots = meeting.slots.copy() if meeting.slots else []

        for slot in current_slots:
            if UUID(slot.get("user_id")) == user.id:
                current_slots.remove(slot)
                break
        else:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Slots for this user not found in this meeting",
            )

        current_slots.append({name: slots, "user_id": str(user.id)})

        meeting.slots = current_slots

        self.session.add(meeting)
        await self.session.flush()

    # А еще думаю, здесь нужно удалять связь между пользователем и встречей
    async def delete_slots_of_user(
        self, id: UUID, username: str, user: UserSchema | None
    ):
        query: Select = select(Meetings).options(selectinload(Meetings.participants)).where(Meetings.id == id)
        result: AsyncResult = await self.session.execute(query)
        meeting: Meetings = result.scalar_one_or_none()

        if not meeting:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Meeting not found"
            )

        if not user:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to delete slots of this meeting",
            )

        if user.id != meeting.owner_id:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="You are not the owner of this meeting",
            )

        current_slots = meeting.slots.copy() if meeting.slots else []

        for slot in current_slots:
            for key, _ in slot.items():
                if key == username:
                    current_slots.remove(slot)
                    # По сути, здесь уже точно у slot должен быть user_id
                    if user := await self.session.get(Users, slot["user_id"]):
                        if user in meeting.participants:
                            meeting.participants.remove(user)
                    elif slot["user_id"] is not None:  # Если user_id есть, но пользователя нет, то это странно, но все же обработаем этот кейс
                        raise HTTPException(
                            status_code=HTTP_404_NOT_FOUND, detail="User not found"
                        )
                    break
            else:
                continue
            break
        else:
            # Вот эта ошибка хер возникнет конечно, так как вряд ли от Кирюхи такое придет
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Slots for this user not found in this meeting",
            )

        meeting.slots = current_slots

        self.session.add(meeting)
        await self.session.flush()
