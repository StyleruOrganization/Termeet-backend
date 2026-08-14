from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

from backend.src.users.schemas import UserSchema
from backend.src.meetings.infrastructure import Infrastructure
from backend.src.meetings.live import meet_live_hub
from backend.src.meetings.permissions import (
    can_delete_participants,
    can_edit_meet,
    can_edit_settings,
    can_set_final,
    can_vote,
    has_final_slot,
    has_user_slots,
    is_owner,
    observer_user_ids,
    organizer_slot_name,
)
from backend.src.meetings.schemas import (
    MeetPermissions,
    MeetResponse,
    MeetCreate,
    MeetFinalUpdate,
    MeetSettingsUpdate,
    ObserverUser,
    SlotsUser,
    UserMeetingItem,
)

if TYPE_CHECKING:
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
            and not has_final_slot(record)
        )
        return MeetPermissions(
            can_edit_meet=can_edit_meet(record, user),
            can_delete_participants=can_delete_participants(record, user),
            can_edit_settings=can_edit_settings(record, user),
            can_vote=can_vote(record, user),
            can_observe=can_observe,
            can_set_final=can_set_final(record, user),
            is_observer=is_observer,
        )

    def _to_response(
        self, record: "Meetings", user: UserSchema | None
    ) -> MeetResponse:
        slots = record.slots if isinstance(record.slots, list) else []
        invited = (
            record.invited_user_ids
            if isinstance(record.invited_user_ids, list)
            else []
        )
        meeting = MeetResponse.model_validate(
            {
                "id": record.id,
                "name": record.name,
                "description": record.description,
                "link": record.link,
                "duration": record.duration,
                "data_range": record.data_range or [],
                "invited_user_ids": [str(item) for item in invited],
                "slots": slots,
                "anyone_can_edit": record.anyone_can_edit,
                "anyone_can_delete_participants": (
                    record.anyone_can_delete_participants
                ),
                "require_login_to_vote": record.require_login_to_vote,
                "anyone_can_set_final": record.anyone_can_set_final,
                "final_slot": record.final_slot,
                "observers": [],
            }
        )
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
            if isinstance(item, dict)
        ]
        if meeting.is_creator:
            meeting.observers = observers
        else:
            meeting.observers = []
        return meeting

    async def notify_live(self, meeting_id: UUID) -> None:
        try:
            record = await self.repository.get_meeting(meeting_id)
            await meet_live_hub.publish(record, self._to_response)
        except Exception:
            return

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
        meeting.data_range = record.data_range

        if not can_edit_meet(record, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to edit this meeting",
            )

        await self.repository.edit_meeting(record, meeting)
        await self.notify_live(hash)
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
        await self.notify_live(hash)
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
        await self.notify_live(hash)
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

        if has_final_slot(record):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Final time is already set",
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
        await self.notify_live(hash)
        return {"detail": "Slots added successfully"}

    async def edit_slots(
        self, hash: UUID, slots: SlotsUser, user: UserSchema | None
    ):
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to edit slots",
            )

        record: Meetings = await self.repository.get_meeting(hash)
        if has_final_slot(record):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Final time is already set",
            )

        await self.repository.edit_slots(hash, slots.name, slots.slots, user)
        await self.notify_live(hash)
        return {"detail": "Slots edited successfully"}

    async def set_final(
        self,
        hash: UUID,
        payload: MeetFinalUpdate,
        user: UserSchema | None,
    ) -> MeetResponse:
        record: Meetings = await self.repository.get_meeting(hash)
        if not can_set_final(record, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to set final time",
            )
        if not payload.slots:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select final time first",
            )
        await self.repository.set_final_slot(record, payload.slots)
        await self.notify_live(hash)
        return self._to_response(record, user)

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
        await self.notify_live(hash)
        return {"detail": "Slots deleted successfully"}
