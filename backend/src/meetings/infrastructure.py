from uuid import UUID
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from backend.src.meetings.repositories import Repository
from backend.src.meetings.models import Meetings
from backend.src.users.schemas import UserSchema
from backend.src.users.models import Users  # noqa:
from backend.src.teams.models import Teams  # noqa:

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, AsyncResult
    from sqlalchemy import Select
    from backend.src.meetings.schemas import MeetCreate


class Infrastructure(Repository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_cached_user(self, user: UserSchema) -> Optional[Users]:
        user_cache = self.session.info.get("user_cache", {})
        cached_user: Users = user_cache.get(user.id)

        return cached_user

    async def get_meeting_with_participants(self, id: UUID) -> Meetings:
        query: Select = (
            select(Meetings)
            .options(selectinload(Meetings.participants))
            .where(Meetings.id == id)
        )
        result: AsyncResult = await self.session.execute(query)
        meeting: Meetings = result.scalar_one_or_none()

        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found",
            )

        return meeting

    async def get_meeting(self, id: UUID) -> Meetings:
        record: Meetings | None = await self.session.get(Meetings, id)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found",
            )

        return record

    async def create_meeting(
        self, meeting: MeetCreate, user: UserSchema | None
    ) -> Optional[Meetings]:

        object: Meetings = Meetings(**meeting.model_dump(by_alias=True))

        if user:
            # Достаем пользователя из словаря сессии
            cached_user = await self.get_cached_user(user)
            object.owner = cached_user

        self.session.add(object)
        await self.session.flush()
        return object

    async def edit_meeting(
        self, record: Meetings, meeting: MeetCreate
    ) -> Optional[Meetings]:

        for key, value in meeting.model_dump().items():
            setattr(record, key, value)

        record.data_range = meeting.dataRange

        self.session.add(record)
        await self.session.flush()
        return record

    async def add_slots(
        self, name: str, slots: list, meeting: Meetings, user: Users | None
    ):

        if user:
            meeting.participants.append(user)

        current_slots = meeting.slots.copy() if meeting.slots else []

        current_slots.append(
            {"name": name,
             "slots": slots,
             "user_id": str(user.id) if user else None}
        )

        meeting.slots = current_slots

        self.session.add(meeting)
        await self.session.flush()

    async def edit_slots(
        self, id: UUID, name: str, slots: list, user: UserSchema | None
    ):
        meeting: Meetings = await self.get_meeting_with_participants(id)

        # Достаем пользователя из словаря сессии
        cached_user = await self.get_cached_user(user)

        if cached_user not in meeting.participants:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant of this meeting",
            )

        current_slots = meeting.slots.copy() if meeting.slots else []

        for slot in current_slots:
            if slot.get("user_id") == str(user.id):
                current_slots.remove(slot)
                break
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slots for this user not found in this meeting",
            )

        current_slots.append(
            {"name": name,
             "slots": slots,
             "user_id": str(user.id) if user else None}
        )

        meeting.slots = current_slots

        self.session.add(meeting)
        await self.session.flush()

    async def delete_slots_of_user(
        self, meeting: Meetings, username: str, user: UserSchema | None
    ):

        current_slots = meeting.slots.copy() if meeting.slots else []

        for slot in current_slots:
            if username == slot["name"]:

                if (slot["user_id"] is not None):
                    if user := (await self.session.get(Users, slot["user_id"])):
                        meeting.participants.remove(user)
                        # Такого по сути быть не может, но оставил потому что это поле
                        # хранится в JSONB и если пользователь удалится,
                        # то может остаться "мертвый" user_id в слотах,
                        # который будет мешать удалению слотов
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found",
                        )

                current_slots.remove(slot)
                break
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slots for this user not found in this meeting",
            )

        meeting.slots = current_slots

        self.session.add(meeting)
        await self.session.flush()
