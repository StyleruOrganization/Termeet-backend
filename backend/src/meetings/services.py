from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

from backend.src.integrations.yandex_calendar import (
    build_ics,
    delete_event,
    event_uid,
    events_overlap,
    has_calendar_scope,
    list_events,
    upsert_event,
)
from backend.src.integrations.yandex_telemost import yandex_account_from_user
from backend.src.notifications.meet_emails import (
    format_range,
    meet_url,
    notify_calendar_conflict,
    notify_final_time,
    notify_owner_participant_voted,
)
from backend.src.users.models import Users
from backend.src.users.schemas import UserSchema
from backend.src.meetings.infrastructure import Infrastructure
from backend.src.meetings.live import meet_live_hub
from backend.src.meetings.permissions import (
    can_delete_participants,
    can_edit_meet,
    can_edit_settings,
    can_set_final,
    can_view_meeting,
    can_vote,
    has_final_slot,
    has_user_slots,
    is_owner,
    lock_vote_after_deadline,
    observer_user_ids,
    organizer_slot_name,
    vote_deadline_passed,
)
from backend.src.meetings.schemas import (
    CalendarConflict,
    CalendarSyncInfo,
    MeetPermissions,
    MeetResponse,
    MeetCreate,
    MeetFinalUpdate,
    MeetSettingsUpdate,
    ObserverUser,
    OrganizerContacts,
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

    def _organizer_contacts(self, owner) -> OrganizerContacts | None:
        if owner is None:
            return None
        return OrganizerContacts(
            email=getattr(owner, "contact_email", None)
            or getattr(owner, "email", None),
            telegram=getattr(owner, "contact_telegram", None),
            vk=getattr(owner, "contact_vk", None),
        )

    def _organizer_display_name(self, owner) -> str | None:
        if owner is None:
            return None
        name = f"{owner.first_name} {owner.last_name}".strip()
        return name or None

    def _to_response(
        self,
        record: "Meetings",
        user: UserSchema | None,
        access_denied: bool = False,
    ) -> MeetResponse:
        if access_denied:
            owner = getattr(record, "owner", None)
            meeting = MeetResponse.model_validate(
                {
                    "id": record.id,
                    "name": record.name,
                    "description": None,
                    "link": None,
                    "duration": None,
                    "data_range": [],
                    "invited_user_ids": [],
                    "slots": [],
                    "anyone_can_edit": False,
                    "anyone_can_delete_participants": False,
                    "require_login_to_vote": True,
                    "anyone_can_set_final": False,
                    "final_slot": None,
                    "observers": [],
                    "is_closed": True,
                    "invite_only_vote": True,
                    "team_id": record.team_id,
                    "team_name": getattr(record.team, "name", None)
                    if record.team
                    else None,
                    "access_denied": True,
                    "vote_deadline": None,
                    "remind_enabled": False,
                    "remind_offsets": [],
                    "lock_vote_after_deadline": False,
                }
            )
            meeting.is_creator_auth = record.owner_id is not None
            meeting.is_creator = False
            meeting.organizer_name = self._organizer_display_name(owner)
            meeting.organizer_contacts = self._organizer_contacts(owner)
            meeting.permissions = MeetPermissions(
                can_edit_meet=False,
                can_delete_participants=False,
                can_edit_settings=False,
                can_vote=False,
                can_observe=False,
                can_set_final=False,
                is_observer=False,
            )
            return meeting

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
                "is_closed": bool(getattr(record, "is_closed", False)),
                "invite_only_vote": bool(
                    getattr(record, "invite_only_vote", False)
                ),
                "team_id": record.team_id,
                "team_name": getattr(record.team, "name", None)
                if getattr(record, "team", None)
                else None,
                "vote_deadline": getattr(record, "vote_deadline", None),
                "remind_enabled": bool(
                    getattr(record, "remind_enabled", False)
                ),
                "remind_offsets": list(
                    getattr(record, "remind_offsets", None) or []
                ),
                "lock_vote_after_deadline": bool(
                    getattr(record, "lock_vote_after_deadline", False)
                ),
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
        if not can_view_meeting(record, user):
            return self._to_response(record, user, access_denied=True)
        return self._to_response(record, user)

    async def create_meeting(
        self, meeting: MeetCreate, user: UserSchema | None
    ) -> MeetResponse:
        if not user:
            meeting.team_id = None
            meeting.is_closed = False
            meeting.invite_only_vote = False
        elif meeting.team_id:
            from backend.src.teams.services import Service as TeamService

            teams = TeamService(self.repository.session)
            team = await teams.repository.get_team(meeting.team_id)
            if not teams._can_see(team, user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot create a meeting with this team",
                )
            invited = {
                str(item) for item in (meeting.invited_user_ids or []) if item
            }
            invited.add(str(team.user_id))
            for member in team.members or []:
                invited.add(str(member.id))
            invited.discard(str(user.id))
            meeting.invited_user_ids = list(invited)
        if meeting.is_closed:
            meeting.invite_only_vote = True
        elif not meeting.team_id:
            meeting.invite_only_vote = False
        record: Meetings = await self.repository.create_meeting(meeting, user)
        if user and meeting.add_to_calendar:
            synced = await self._add_meeting_to_calendar(record, user)
            response = self._to_response(record, user)
            response.calendar_sync = CalendarSyncInfo(synced=int(synced))
            return response
        return self._to_response(record, user)

    async def _notify_owner_vote(
        self,
        record: "Meetings",
        participant_name: str,
        voter: UserSchema | None,
    ) -> None:
        if not record.owner_id:
            return
        if voter and str(voter.id) == str(record.owner_id):
            return
        owner = record.owner
        if owner is None:
            owner = await self.repository.session.get(Users, record.owner_id)
        if owner is None:
            return
        await notify_owner_participant_voted(
            owner.email,
            getattr(owner, "notify_on_vote", True),
            record.name,
            record.id,
            participant_name,
        )

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
            if lock_vote_after_deadline(record) and vote_deadline_passed(
                record
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Voting deadline has passed",
                )
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
        await self._notify_owner_vote(record, slots.name, user)
        return {"detail": "Slots added successfully"}

    async def edit_slots(
        self, hash: UUID, slots: SlotsUser, user: UserSchema | None
    ):
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to edit slots",
            )

        record: Meetings = await self.repository.get_meeting_with_participants(
            hash
        )
        if has_final_slot(record):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Final time is already set",
            )
        if lock_vote_after_deadline(record) and vote_deadline_passed(record):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voting deadline has passed",
            )

        await self.repository.edit_slots(hash, slots.name, slots.slots, user)
        await self.notify_live(hash)
        await self._notify_owner_vote(record, slots.name, user)
        return {"detail": "Slots edited successfully"}

    async def set_final(
        self,
        hash: UUID,
        payload: MeetFinalUpdate,
        user: UserSchema | None,
    ) -> MeetResponse:
        record: Meetings = await self.repository.get_meeting_with_participants(
            hash
        )
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
        was_set = has_final_slot(record)
        await self.repository.set_final_slot(record, payload.slots)
        await self.notify_live(hash)
        sync = await self._sync_final_calendars(
            record, payload.slots, user, changed=was_set
        )
        response = self._to_response(record, user)
        response.calendar_sync = sync
        return response

    def _parse_iso(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _cell_keys(self, ranges) -> set[str]:
        keys: set[str] = set()
        for item in ranges or []:
            if not item or len(item) < 2:
                continue
            start = self._parse_iso(item[0])
            end = self._parse_iso(item[1])
            current = start
            while current <= end:
                keys.add(current.strftime("%Y-%m-%dT%H:%M"))
                current += timedelta(minutes=30)
        return keys

    def _final_span(self, slots) -> tuple[datetime, datetime] | None:
        starts: list[datetime] = []
        ends: list[datetime] = []
        for item in slots or []:
            if not item or len(item) < 2:
                continue
            starts.append(self._parse_iso(item[0]))
            ends.append(self._parse_iso(item[1]))
        if not starts:
            return None
        return min(starts), max(ends) + timedelta(minutes=30)

    def _duration_minutes(self, text: str | None) -> int:
        raw = (text or "").lower().replace(" ", "")
        table = {
            "30мин": 30,
            "1час": 60,
            "1,5часа": 90,
            "1.5часа": 90,
            "2часа": 120,
            "2,5часа": 150,
            "2.5часа": 150,
            "3часа": 180,
        }
        return table.get(raw, 60)

    def _placeholder_span(
        self, record: "Meetings"
    ) -> tuple[datetime, datetime] | None:
        ranges = record.data_range or []
        if not ranges:
            return None
        first = ranges[0]
        if not first or len(first) < 1:
            return None
        start = self._parse_iso(first[0])
        minutes = self._duration_minutes(record.duration)
        return start, start + timedelta(minutes=minutes)

    async def _add_meeting_to_calendar(
        self, record: "Meetings", user: UserSchema
    ) -> bool:
        person = await self.repository.get_user_with_oauth(user.id)
        if person is None:
            return False
        account = yandex_account_from_user(person)
        if not has_calendar_scope(account):
            return False
        span = self._placeholder_span(record)
        if span is None:
            return False
        start, end = span
        uid = event_uid(record.id, person.id)
        try:
            href = await upsert_event(
                account,
                uid=uid,
                summary=record.name,
                start=start,
                end=end,
                description=record.description or "",
                url=meet_url(record.id),
                fallback_email=person.email,
            )
        except Exception:
            href = None
        if not href:
            return False
        stored = dict(record.calendar_events or {})
        stored[str(person.id)] = {"uid": uid, "href": href, "sequence": 0}
        record.calendar_events = stored
        self.repository.session.add(record)
        await self.repository.session.flush()
        return True

    async def _sync_final_calendars(
        self,
        record: "Meetings",
        slots,
        actor: UserSchema | None,
        changed: bool,
    ) -> CalendarSyncInfo:
        span = self._final_span(slots)
        if span is None:
            return CalendarSyncInfo()
        start, end = span
        when_text = format_range(start, end)
        ics = build_ics(
            uid=f"termeet-{record.id}@termeet.tech",
            summary=record.name,
            start=start,
            end=end,
            description=record.description or "",
            url=meet_url(record.id),
        )
        final_keys = self._cell_keys(slots)
        attendee_ids: dict[str, str] = {}
        for slot in record.slots or []:
            user_id = slot.get("user_id")
            if not user_id:
                continue
            voted = self._cell_keys(slot.get("slots") or [])
            if final_keys and final_keys.issubset(voted):
                attendee_ids[str(user_id)] = slot.get("name") or "Участник"
        if actor:
            attendee_ids.setdefault(
                str(actor.id),
                f"{actor.first_name} {actor.last_name}".strip() or "Вы",
            )

        stored = dict(record.calendar_events or {})
        synced = 0
        synced_emails: set[str] = set()
        conflicts: list[CalendarConflict] = []
        conflict_emails: set[str] = set()

        for user_id, name in attendee_ids.items():
            try:
                person_id = UUID(str(user_id))
            except (TypeError, ValueError):
                continue
            person = await self.repository.get_user_with_oauth(person_id)
            if person is None:
                continue
            account = yandex_account_from_user(person)
            if not has_calendar_scope(account):
                continue
            uid = event_uid(record.id, person.id)
            busy_titles: list[str] = []
            try:
                existing = await list_events(
                    account,
                    start - timedelta(minutes=1),
                    end + timedelta(minutes=1),
                    fallback_email=person.email,
                )
                for event in existing:
                    if event.uid == uid:
                        continue
                    if events_overlap(start, end, event.start, event.end):
                        busy_titles.append(event.title)
            except Exception:
                existing = []
            entry = stored.get(str(person.id))
            href = None
            sequence = 1
            if isinstance(entry, dict):
                href = entry.get("href")
                try:
                    sequence = int(entry.get("sequence") or 0) + 1
                except (TypeError, ValueError):
                    sequence = 1
            if sequence < 1:
                sequence = 1
            try:
                saved_href = await upsert_event(
                    account,
                    uid=uid,
                    summary=record.name,
                    start=start,
                    end=end,
                    description=record.description or "",
                    url=meet_url(record.id),
                    href=href,
                    fallback_email=person.email,
                    sequence=sequence,
                )
            except Exception:
                saved_href = None
            if saved_href:
                stored[str(person.id)] = {
                    "uid": uid,
                    "href": saved_href,
                    "sequence": sequence,
                }
                synced += 1
                if person.email:
                    synced_emails.add(person.email.lower())
            if busy_titles:
                conflicts.append(
                    CalendarConflict(name=name, titles=busy_titles[:5])
                )
                if person.email and getattr(
                    person, "notify_on_final", True
                ):
                    conflict_emails.add(person.email)
                    await notify_calendar_conflict(
                        person.email,
                        record.name,
                        record.id,
                        when_text,
                        busy_titles[:5],
                        record.link,
                        ics_content=None if saved_href else ics,
                    )

        keep_ids = set(attendee_ids.keys())
        for stored_id in list(stored.keys()):
            if stored_id in keep_ids:
                continue
            leftover = stored.get(stored_id)
            href = leftover.get("href") if isinstance(leftover, dict) else None
            try:
                leftover_id = UUID(str(stored_id))
            except (TypeError, ValueError):
                stored.pop(stored_id, None)
                continue
            person = await self.repository.get_user_with_oauth(leftover_id)
            account = yandex_account_from_user(person) if person else None
            if href and has_calendar_scope(account):
                try:
                    await delete_event(
                        account,
                        href,
                        fallback_email=person.email if person else "",
                    )
                except Exception:
                    pass
            stored.pop(stored_id, None)

        record.calendar_events = stored
        self.repository.session.add(record)
        await self.repository.session.flush()

        emails: list[str] = []
        if record.owner and getattr(record.owner, "notify_on_final", True):
            emails.append(record.owner.email)
        for participant in record.participants or []:
            if getattr(participant, "notify_on_final", True):
                emails.append(participant.email)
        for extra in record.emails or []:
            emails.append(extra)
        await notify_final_time(
            emails,
            record.name,
            record.id,
            record.link,
            changed=changed,
            when_text=when_text,
            ics_content=ics,
            skip_emails=conflict_emails,
            skip_ics_emails=synced_emails,
        )
        return CalendarSyncInfo(synced=synced, conflicts=conflicts)

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
