from typing import TYPE_CHECKING

from .infrastructure import Infrastructure
from .schemas import MeetResponse, MeetCreate, SlotsUser

if TYPE_CHECKING:
    from uuid import UUID


class Service:
    def __init__(self, session):
        self.repository = Infrastructure(session)

    async def get_meeting(self, hash: UUID):
        orm_meeting = await self.repository.get_meeting(hash)

        slots = [
            SlotsUser(name=key, slots=value)
            for slot in orm_meeting.slots for key, value in slot.items()
        ]

        pydantic_meeting = MeetResponse(
            name=orm_meeting.name,
            description=orm_meeting.description,
            link=orm_meeting.link,
            duration=orm_meeting.duration,
            dataRange=orm_meeting.data_range,
            hash=orm_meeting.id,
            slots=slots
        )

        return pydantic_meeting

    async def create_meeting(self, meeting: MeetCreate) -> MeetResponse:
        dict_meeting = meeting.model_dump()
        orm_meeting = await self.repository.create_meeting(dict_meeting)
        pydantic_meeting = MeetResponse.model_validate(orm_meeting)
        return pydantic_meeting

    async def edit_meeting(
            self, hash: UUID, meeting: MeetCreate
            ) -> MeetResponse:
        dict_meeting = meeting.model_dump()
        orm_meeting = await self.repository.edit_meeting(hash, dict_meeting)
        pydantic_meeting = MeetResponse.model_validate(orm_meeting)
        return pydantic_meeting

    async def add_slots(self, hash: UUID, slots: SlotsUser):
        await self.repository.add_slots(hash, slots.name, slots.slots)
        return slots
