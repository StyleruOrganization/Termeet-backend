from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from backend.src.users.schemas import UserSchema
from backend.src.meetings.infrastructure import Infrastructure
from backend.src.meetings.permissions import (
    can_delete_participants,
    can_edit_meet,
    can_edit_settings,
    can_vote,
    has_user_slots,
    is_owner,
    observer_user_ids,
    organizer_slot_name,
)
from backend.src.meetings.schemas import (
    MeetPermissions,
    MeetResponse,
    MeetCreate,
    MeetSettingsUpdate,
    ObserverUser,
    SlotsUser,
    UserMeetingItem,
)

if TYPE_CHECKING:
    from uuid import UUID
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.meetings.models import Meetings


class Service:
    def __init__(self, session: AsyncSession = None):
        self.repository = Infrastructure(session)

    def _permissions(
        self, record: "Meetings", user: UserSchema | None
    ) -> MeetPermissions:
        user_id = str(user.id) if user else None
        is_observer = bool(user_id and user_id in observer_user_ids(record))
        voted = has_user_slots(record, user)
        can_observe = bool(
            user
            and not is_owner(record, user)
            and not voted
            and not is_observer
        )
        return MeetPermissions(
            can_edit_meet=can_edit_meet(record, user),
            can_delete_participants=can_delete_participants(record, user),
            can_edit_settings=can_edit_settings(record, user),
            can_vote=can_vote(record, user),
            can_observe=can_observe,
            is_observer=is_observer,
        )

    def _to_response(
        self, record: "Meetings", user: UserSchema | None
    ) -> MeetResponse:
        meeting = MeetResponse.model_validate(record)
        meeting.is_creator_auth = record.owner_id is not None
        meeting.is_creator = is_owner(record, user)
        meeting.organizer_name = organizer_slot_name(record)
        meeting.permissions = self._permissions(record, user)
        observers = [
            ObserverUser(
                name=item.get("name") or "Участник",
                userId=item.get("user_id"),
            )
            for item in (record.observers or [])
        ]
        if meeting.is_creator:
            meeting.observers = observers
        else:
            meeting.observers = []
        return meeting

    async def get_meeting(
        self, hash: UUID, user: UserSchema | None
    ) -> MeetResponse:
        record: Meetings = await self.repository.get_meeting(hash)
        return self._to_response(record, user)

    async def create_meeting(
        self, meeting: MeetCreate, user: UserSchema | None
    ) -> MeetResponse:
        record: Meetings = await self.repository.create_meeting(meeting, user)
        return self._to_response(record, user)

    async def edit_meeting(
        self, hash: UUID, meeting: MeetCreate, user: UserSchema | None
    ):
        record: Meetings = await self.repository.get_meeting(hash)
        meeting.dataRange = record.data_range

        if not can_edit_meet(record, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to edit this meeting",
            )

        await self.repository.edit_meeting(record, meeting)
        return {"detail": "Meeting edited successfully"}

    async def update_settings(
        self,
        hash: UUID,
        settings: MeetSettingsUpdate,
        user: UserSchema | None,
    ) -> MeetResponse:
        record: Meetings = await self.repository.get_meeting(hash)
        if not can_edit_settings(record, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the organizer can change privacy settings",
            )
        await self.repository.update_settings(record, settings)
        return self._to_response(record, user)

    async def observe_meeting(
        self, hash: UUID, user: UserSchema | None
    ) -> MeetResponse:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to observe",
            )
        record: Meetings = await self.repository.get_meeting_with_participants(
            hash
        )
        if is_owner(record, user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organizer cannot observe own meeting",
            )
        if has_user_slots(record, user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already voted in this meeting",
            )
        await self.repository.add_observer(record, user)
        return self._to_response(record, user)

    async def list_user_meetings(
        self, user: UserSchema
    ) -> list[UserMeetingItem]:
        return await self.repository.list_user_meetings(user)

    async def add_slots(
        self, hash: UUID, slots: SlotsUser, user: UserSchema | None
    ):
        record: Meetings = await self.repository.get_meeting_with_participants(
            hash
        )

        if not can_vote(record, user):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to vote",
            )

        if not slots.slots:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select at least one slot",
            )

        if user:
            cached = await self.repository.get_cached_user(user)
            if cached in record.participants:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You have already added slots for this meeting",
                )
            user = cached

        if slots.name in [slot["name"] for slot in (record.slots or [])]:
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

        if not can_delete_participants(record, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete participants",
            )

        owner_name = organizer_slot_name(record)
        if owner_name and username == owner_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organizer cannot be removed from voters this way",
            )

        if user:
            for slot in record.slots or []:
                if slot.get("name") == username and str(
                    slot.get("user_id")
                ) == str(user.id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You cannot delete your own slots this way",
                    )

        await self.repository.delete_slots_of_user(record, username, user)
        return {"detail": "Slots deleted successfully"}
