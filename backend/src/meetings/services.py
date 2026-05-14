from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from backend.src.users.schemas import UserSchema
from backend.src.meetings.infrastructure import Infrastructure
from backend.src.meetings.schemas import (
    MeetResponse,
    MeetCreate,
    SlotsUser,
)

if TYPE_CHECKING:
    from uuid import UUID
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.meetings.models import Meetings


class Service:
    def __init__(self, session: AsyncSession = None):
        self.repository = Infrastructure(session)

    async def get_meeting(
        self, hash: UUID, user: UserSchema | None
    ) -> MeetResponse:
        record: Meetings = await self.repository.get_meeting(hash)
        meeting: MeetResponse = MeetResponse.model_validate(record)

        if record.owner_id is not None:
            meeting.is_creator_auth = True
        else:
            meeting.is_creator_auth = False

        if user and record.owner_id == user.id:
            meeting.is_creator = True
        else:
            meeting.is_creator = False

        return meeting

    async def create_meeting(
        self, meeting: MeetCreate, user: UserSchema | None
    ) -> MeetResponse:
        meeting: Meetings = await self.repository.create_meeting(meeting, user)
        meeting: MeetResponse = MeetResponse.model_validate(meeting)
        return meeting

    async def edit_meeting(
        self, hash: UUID, meeting: MeetCreate, user: UserSchema | None
    ):

        record: Meetings = await self.repository.get_meeting(hash)

        meeting.dataRange = record.data_range

        if (record.owner_id is not None) and (not user or record.owner_id != user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to edit participants",
            )

        await self.repository.edit_meeting(record, meeting)

        return {"detail": "Meeting edited successfully"}

    async def add_slots(
        self, hash: UUID, slots: SlotsUser, user: UserSchema | None
    ):
        record: Meetings = await self.repository.get_meeting_with_participants(
            hash
        )

        if user:
            # Достаем пользователя из словаря сессии
            user = await self.repository.get_cached_user(user)

            if user in record.participants:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You have already added slots for this meeting",
                )

        if slots.name in [slot["name"] for slot in record.slots]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A slot with this name already exists for this meeting",
            )

        await self.repository.add_slots(slots.name, slots.slots, record, user)
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
        record: Meetings = await self.repository.get_meeting_with_participants(
            hash
        )

        if (record.owner_id is not None) and (not user or record.owner_id != user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete participants",
            )

        await self.repository.delete_slots_of_user(record, username, user)
        return {"detail": "Slots deleted successfully"}
