from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from backend.src.users.schemas import UserSchema
from backend.src.meetings.infrastructure import Infrastructure
from backend.src.meetings.schemas import MeetResponse, MeetCreate, SlotsUser

if TYPE_CHECKING:
    from uuid import UUID
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.meetings.models import Meetings


class Service:
    def __init__(self, session: AsyncSession = None):
        self.repository = Infrastructure(session)

    async def get_meeting(self, hash: UUID):
        meeting: Meetings = await self.repository.get_meeting(hash)
        meeting: MeetResponse = MeetResponse.model_validate(meeting)
        return meeting

    async def create_meeting(
        self, meeting: MeetCreate, user: UserSchema | None
    ) -> MeetResponse:
        meeting: Meetings = await self.repository.create_meeting(meeting, user)
        meeting: MeetResponse = MeetResponse.model_validate(meeting)
        return meeting

    async def edit_meeting(
        self, hash: UUID, meeting: MeetCreate, user: UserSchema | None
    ) -> MeetResponse:

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to edit this meeting",
            )

        meeting: Meetings = await self.repository.edit_meeting(
            hash, meeting, user
        )
        meeting: MeetResponse = MeetResponse.model_validate(meeting)
        return {"detail": "Meeting edited successfully"}

    async def add_slots(
        self, hash: UUID, slots: SlotsUser, user: UserSchema | None
    ):
        await self.repository.add_slots(hash, slots.name, slots.slots, user)
        return {"detail": "Slots added successfully"}

    async def edit_slots(
        self, hash: UUID, slots: SlotsUser, user: UserSchema | None
    ):

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to edit slots",
            )

        await self.repository.edit_slots(hash, slots.name, slots.slots, user)
        return {"detail": "Slots edited successfully"}

    async def delete_slots_of_user(
        self, hash: UUID, username: str, user: UserSchema | None
    ):
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to delete slots",
            )

        await self.repository.delete_slots_of_user(hash, username, user)
        return {"detail": "Slots deleted successfully"}
