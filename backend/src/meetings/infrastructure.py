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
        self, meeting: MeetCreate, user: UserSchema | None = None
    ) -> Optional[Meetings]:

        payload = meeting.model_dump()
        invited = payload.pop("invited_user_ids", None)
        payload.pop("dataRange", None)

        object: Meetings = Meetings(
            **payload,
            data_range=meeting.dataRange or [],
        )

        if invited:
            object.invited_user_ids = [str(item) for item in invited]

        if user:
            # Достаем пользователя из словаря сессии
            cached_user = await self.get_cached_user(user)
            object.owner = cached_user
            object.anyone_can_edit = False
            object.anyone_can_delete_participants = False
            object.require_login_to_vote = False
            object.anyone_can_set_final = False

        self.session.add(object)
        await self.session.flush()
        return object

    async def edit_meeting(
        self, record: Meetings, meeting: MeetCreate
    ) -> Optional[Meetings]:

        for key, value in meeting.model_dump().items():
            if key in ("dataRange", "invited_user_ids"):
                continue
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
            observers = list(meeting.observers or [])
            meeting.observers = [
                item
                for item in observers
                if str(item.get("user_id")) != str(user.id)
            ]

        current_slots = meeting.slots.copy() if meeting.slots else []

        current_slots.append(
            {
                "name": name,
                "slots": slots,
                "user_id": str(user.id) if user else None,
            }
        )

        meeting.slots = current_slots

        self.session.add(meeting)
        await self.session.flush()

    async def edit_slots(
        self, id: UUID, name: str, slots: list, user: UserSchema | None
    ):
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to edit slots",
            )

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

        if slots:
            current_slots.append(
                {
                    "name": name,
                    "slots": slots,
                    "user_id": str(user.id) if user else None,
                }
            )
        elif cached_user and cached_user in (meeting.participants or []):
            meeting.participants.remove(cached_user)

        meeting.slots = current_slots

        self.session.add(meeting)
        await self.session.flush()

    async def update_settings(self, meeting: Meetings, settings) -> Meetings:
        meeting.anyone_can_edit = settings.anyone_can_edit
        meeting.anyone_can_delete_participants = (
            settings.anyone_can_delete_participants
        )
        meeting.require_login_to_vote = settings.require_login_to_vote
        if settings.anyone_can_set_final is not None:
            meeting.anyone_can_set_final = settings.anyone_can_set_final
        self.session.add(meeting)
        await self.session.flush()
        return meeting

    async def add_observer(self, meeting: Meetings, user: UserSchema):
        observers = list(meeting.observers or [])
        user_id = str(user.id)
        if any(str(item.get("user_id")) == user_id for item in observers):
            return
        observers.append(
            {
                "user_id": user_id,
                "name": f"{user.first_name} {user.last_name}".strip(),
            }
        )
        meeting.observers = observers
        self.session.add(meeting)
        await self.session.flush()

    async def set_final_slot(self, meeting: Meetings, slots: list) -> Meetings:
        from datetime import datetime, timedelta

        def parse_dt(value: str) -> datetime:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        def cell_keys(ranges: list) -> tuple[set[str], set[str]]:
            keys: set[str] = set()
            days: set[str] = set()
            for item in ranges or []:
                if not item or len(item) < 2:
                    continue
                start = parse_dt(item[0])
                end = parse_dt(item[1])
                current = start
                while current <= end:
                    days.add(current.date().isoformat())
                    keys.add(current.strftime("%Y-%m-%dT%H:%M"))
                    current += timedelta(minutes=30)
            return keys, days

        voted: set[str] = set()
        for slot in meeting.slots or []:
            keys, _ = cell_keys(slot.get("slots") or [])
            voted.update(keys)

        final_keys, final_days = cell_keys(slots)
        if len(final_days) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Final time must be on a single day",
            )
        if not final_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select final time first",
            )
        if not final_keys.issubset(voted):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Final time must be among slots people already voted",
            )

        meeting.final_slot = slots
        self.session.add(meeting)
        await self.session.flush()
        return meeting

    def _to_meeting_item(self, meeting: Meetings, role: str):
        from backend.src.meetings.schemas import UserMeetingItem

        names = [
            slot.get("name")
            for slot in (meeting.slots or [])
            if slot.get("name")
        ]
        return UserMeetingItem(
            hash=meeting.id,
            name=meeting.name,
            description=meeting.description,
            duration=meeting.duration,
            link=meeting.link,
            role=role,
            data_range=meeting.data_range or [],
            has_final=bool(meeting.final_slot),
            participant_names=names,
            participant_count=len(names),
        )

    async def list_user_meetings(self, user: UserSchema):
        from sqlalchemy import select

        from backend.src.meetings.models import MeetingsUsers
        from backend.src.meetings.schemas import UserMeetingItem

        uid = user.id
        uid_str = str(uid)
        items: dict[str, UserMeetingItem] = {}

        owned = await self.session.execute(
            select(Meetings).where(Meetings.owner_id == uid)
        )
        for meeting in owned.scalars().all():
            items[str(meeting.id)] = self._to_meeting_item(meeting, "owner")

        participated = await self.session.execute(
            select(Meetings)
            .join(
                MeetingsUsers, MeetingsUsers.meeting_id == Meetings.id
            )
            .where(MeetingsUsers.user_id == uid)
        )
        for meeting in participated.scalars().all():
            key = str(meeting.id)
            if key not in items:
                items[key] = self._to_meeting_item(meeting, "participant")

        observed = await self.session.execute(
            select(Meetings).where(
                Meetings.observers.contains([{"user_id": uid_str}])
            )
        )
        for meeting in observed.scalars().all():
            key = str(meeting.id)
            if key not in items:
                items[key] = self._to_meeting_item(meeting, "observer")

        invited = await self.session.execute(
            select(Meetings).where(
                Meetings.invited_user_ids.contains([uid_str])
            )
        )
        for meeting in invited.scalars().all():
            key = str(meeting.id)
            if key not in items:
                items[key] = self._to_meeting_item(meeting, "invited")

        return list(items.values())

    async def delete_slots_of_user(
        self, meeting: Meetings, username: str, user: UserSchema | None
    ):

        current_slots = meeting.slots.copy() if meeting.slots else []

        for slot in current_slots:
            if username == slot["name"]:

                if slot["user_id"] is not None:
                    if user := (
                        await self.session.get(Users, slot["user_id"])
                    ):
                        meeting.participants.remove(user)
                        # Такого по сути быть не может,
                        # но оставил потому что это поле
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
