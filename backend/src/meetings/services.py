from typing import TYPE_CHECKING

from backend.src.users.schemas import UserSchema
from .infrastructure import Infrastructure
from .schemas import MeetResponse, MeetCreate, SlotsUser

if TYPE_CHECKING:
    from uuid import UUID
    from sqlalchemy.ext.asyncio import AsyncSession


class Service:
    def __init__(self, session: AsyncSession = None):
        self.repository = Infrastructure(session)

    async def get_meeting(self, hash: UUID):
        orm_meeting = await self.repository.get_meeting(hash)

        # Теперь здесь нужно добавить проврку user_id
        slots = [
            SlotsUser(name=key, slots=value)
            for slot in orm_meeting.slots
            for key, value in slot.items()
            if key != "user_id"  # Исключаем user_id из слотов
        ]

        pydantic_meeting = MeetResponse(
            name=orm_meeting.name,
            description=orm_meeting.description,
            link=orm_meeting.link,
            duration=orm_meeting.duration,
            dataRange=orm_meeting.data_range,
            hash=orm_meeting.id,
            slots=slots,
        )

        return pydantic_meeting

    async def create_meeting(
        self, meeting: MeetCreate, user: UserSchema | None
    ) -> MeetResponse:
        orm_meeting = await self.repository.create_meeting(meeting, user)
        pydantic_meeting = MeetResponse.model_validate(orm_meeting)
        return pydantic_meeting

    async def edit_meeting(
        self, hash: UUID, meeting: MeetCreate, user: UserSchema | None
    ) -> MeetResponse:
        orm_meeting = await self.repository.edit_meeting(hash, meeting, user)
        slots = [
            SlotsUser(name=key, slots=value)
            for slot in orm_meeting.slots
            for key, value in slot.items()
            if key != "user_id"  # Исключаем user_id из слотов
        ]

        pydantic_meeting = MeetResponse(
            name=orm_meeting.name,
            description=orm_meeting.description,
            link=orm_meeting.link,
            duration=orm_meeting.duration,
            dataRange=orm_meeting.data_range,
            hash=orm_meeting.id,
            slots=slots,
        )

        return pydantic_meeting

    async def add_slots(
        self, hash: UUID, slots: SlotsUser, user: UserSchema | None
    ):
        await self.repository.add_slots(hash, slots.name, slots.slots, user)
        return slots

    async def edit_slots(
        self, hash: UUID, slots: SlotsUser, user: UserSchema | None
    ):
        await self.repository.edit_slots(hash, slots.name, slots.slots, user)
        return slots

    async def delete_slots_of_user(
        self, hash: UUID, username: str, user: UserSchema | None
    ):
        await self.repository.delete_slots_of_user(hash, username, user)
        return {"detail": "Slots deleted successfully"}
