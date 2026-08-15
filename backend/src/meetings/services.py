from html import escape
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
from backend.src.notifications.telegram import send_telegram_message
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
    expected_voter_ids,
    has_final_slot,
    has_user_slots,
    invited_user_ids,
    is_owner,
    lock_vote_after_deadline,
    observer_user_ids,
    team_member_ids,
    organizer_slot_name,
    vote_deadline_passed,
    voted_user_ids,
)
from backend.src.meetings.suggest_final import suggest_windows
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
    InvitedUser,
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
                    "organizer_contacts": None,
                    "invited_users": [],
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

    async def _invited_people(self, record: "Meetings") -> list[InvitedUser]:
        ids = [str(item) for item in (record.invited_user_ids or []) if item]
        if not ids:
            return []
        people = await self.repository.list_users_by_ids(ids)
        by_id = {str(person.id): person for person in people}
        result: list[InvitedUser] = []
        for uid in ids:
            person = by_id.get(uid)
            if person is None:
                continue
            result.append(
                InvitedUser(
                    id=person.id,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    has_avatar=bool(getattr(person, "avatar_key", None)),
                )
            )
        return result

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
        meeting = self._to_response(record, user)
        if meeting.is_creator:
            meeting.invited_users = await self._invited_people(record)
        return meeting

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
        await self._notify_invited_telegram(
            record,
            {str(item) for item in (record.invited_user_ids or []) if item},
        )
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
        if not getattr(owner, "notify_on_vote", True):
            return
        href = meet_url(record.id)
        if getattr(owner, "notify_email", True):
            await notify_owner_participant_voted(
                owner.email,
                True,
                record.name,
                record.id,
                participant_name,
            )
        if getattr(owner, "notify_telegram", True):
            await send_telegram_message(
                getattr(owner, "telegram_user_id", None),
                f"На встрече «{record.name}» время отметил: "
                f"{participant_name}\n{href}",
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

        old_invited = {
            str(item) for item in (record.invited_user_ids or []) if item
        }
        await self.repository.edit_meeting(record, meeting)
        await self.notify_live(hash)
        new_invited = {
            str(item) for item in (record.invited_user_ids or []) if item
        }
        await self._notify_invited_telegram(record, new_invited - old_invited)
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

        before_all = self._all_expected_voted(record)
        await self.repository.add_slots(slots.name, slots.slots, record, user)
        await self.notify_live(hash)
        await self._notify_owner_vote(record, slots.name, user)
        if not before_all and self._all_expected_voted(record):
            await self._notify_owner_all_voted(record)
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
            if getattr(record.owner, "notify_email", True):
                emails.append(record.owner.email)
            if getattr(record.owner, "notify_telegram", True):
                await send_telegram_message(
                    getattr(record.owner, "telegram_user_id", None),
                    f"Назначили время встречи «{record.name}»\n"
                    f"{meet_url(record.id)}",
                )
        for participant in record.participants or []:
            if getattr(participant, "notify_on_final", True):
                if getattr(participant, "notify_email", True):
                    emails.append(participant.email)
                if getattr(participant, "notify_telegram", True):
                    await send_telegram_message(
                        getattr(participant, "telegram_user_id", None),
                        f"Назначили время встречи «{record.name}»\n"
                        f"{meet_url(record.id)}",
                    )
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

    def _telegram_push_ids(self, record: "Meetings") -> set[str]:
        ids: set[str] = set()
        for person in record.participants or []:
            ids.add(str(person.id))
        for slot in record.slots or []:
            if isinstance(slot, dict) and slot.get("user_id"):
                ids.add(str(slot["user_id"]))
        ids |= invited_user_ids(record)
        ids |= team_member_ids(record)
        if record.owner_id:
            ids.discard(str(record.owner_id))
        ids -= observer_user_ids(record)
        return ids

    async def push_telegram(
        self,
        hash: UUID,
        user: UserSchema,
        note: str | None,
        only_pending: bool = False,
    ) -> dict:
        from backend.src.config import config

        if not (config.telegram_bot.TOKEN or "").strip():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram bot token is not configured",
            )
        record: Meetings = await self.repository.get_meeting_with_participants(
            hash
        )
        if not is_owner(record, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the organizer can push this meeting",
            )
        recipient_ids = self._telegram_push_ids(record)
        pending_empty = False
        if only_pending:
            expected = expected_voter_ids(record)
            pending = expected - voted_user_ids(record)
            if not expected:
                pending_empty = True
                recipient_ids = set()
            else:
                recipient_ids &= pending
        people = await self.repository.list_users_by_ids(list(recipient_ids))
        title = escape(record.name or "Встреча")
        href = meet_url(record.id)
        extra = (note or "").strip()
        if extra:
            body = (
                f"Организатор по встрече «{title}»:\n\n"
                f"{escape(extra)}\n\n{href}"
            )
        elif only_pending:
            body = (
                f"Организатор ждёт, когда вы отметите время "
                f"на встрече «{title}».\n{href}"
            )
        else:
            body = (
                f"Организатор просит отметить время "
                f"на встрече «{title}».\n{href}"
            )
        sent = 0
        muted = 0
        no_telegram = 0
        for person in people:
            if not getattr(person, "telegram_user_id", None):
                no_telegram += 1
                continue
            if not getattr(person, "notify_telegram", True):
                muted += 1
                continue
            ok = await send_telegram_message(person.telegram_user_id, body)
            if ok:
                sent += 1
        return {
            "sent": sent,
            "muted": muted,
            "no_telegram": no_telegram,
            "name": record.name,
            "pending_empty": pending_empty,
        }

    def _all_expected_voted(self, record: "Meetings") -> bool:
        expected = expected_voter_ids(record)
        if not expected:
            return False
        return expected <= voted_user_ids(record)

    async def _notify_owner_all_voted(self, record: "Meetings") -> None:
        owner = record.owner
        if owner is None and record.owner_id:
            owner = await self.repository.session.get(Users, record.owner_id)
        if owner is None:
            return
        if not getattr(owner, "notify_telegram", True):
            return
        href = meet_url(record.id)
        title = escape(record.name or "Встреча")
        await send_telegram_message(
            getattr(owner, "telegram_user_id", None),
            f"На встрече «{title}» все из списка отметили время. "
            f"Можно назначить итог в боте или на сайте.\n{href}",
        )

    async def _notify_invited_telegram(
        self, record: "Meetings", user_ids: set[str]
    ) -> None:
        if not user_ids:
            return
        people = await self.repository.list_users_by_ids(list(user_ids))
        href = meet_url(record.id)
        title = escape(record.name or "Встреча")
        for person in people:
            if not getattr(person, "notify_telegram", True):
                continue
            await send_telegram_message(
                getattr(person, "telegram_user_id", None),
                f"Вас пригласили на встречу «{title}». "
                f"Отметьте удобное время:\n{href}",
            )

    async def bot_status(
        self, hash: UUID, user: UserSchema
    ) -> dict:
        record: Meetings = await self.repository.get_meeting_with_participants(
            hash
        )
        if not is_owner(record, user) and not any(
            str(slot.get("user_id")) == str(user.id)
            for slot in (record.slots or [])
            if isinstance(slot, dict)
        ):
            if str(user.id) not in invited_user_ids(
                record
            ) and str(user.id) not in team_member_ids(record):
                if str(user.id) not in observer_user_ids(record):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You cannot see this meeting",
                    )
        owner = is_owner(record, user)
        voted_names = [
            str(slot.get("name"))
            for slot in (record.slots or [])
            if isinstance(slot, dict) and slot.get("name")
        ]
        guest_count = sum(
            1
            for slot in (record.slots or [])
            if isinstance(slot, dict)
            and slot.get("name")
            and not slot.get("user_id")
        )
        pending_people: list[dict] = []
        expected_count = 0
        if owner:
            expected = expected_voter_ids(record)
            expected_count = len(expected)
            pending_ids = expected - voted_user_ids(record)
            pending_users = await self.repository.list_users_by_ids(
                list(pending_ids)
            )
            pending_people = [
                {
                    "name": f"{item.first_name} {item.last_name}".strip()
                    or "Участник",
                    "has_telegram": bool(
                        getattr(item, "telegram_user_id", None)
                    ),
                }
                for item in pending_users
            ]
        final_label = None
        if record.final_slot:
            span = self._final_span(record.final_slot)
            if span:
                final_label = format_range(span[0], span[1])
        suggestions = []
        if owner and not has_final_slot(record):
            suggestions = suggest_windows(
                record.slots, record.duration, limit=3
            )
        has_final = has_final_slot(record)
        return {
            "hash": record.id,
            "name": record.name,
            "is_owner": owner,
            "has_final": has_final,
            "final_label": final_label,
            "voted": voted_names,
            "pending": pending_people,
            "guest_count": guest_count,
            "expected_count": expected_count,
            "can_nudge": owner and not has_final and bool(pending_people),
            "can_set_final": owner and not has_final and bool(suggestions),
            "suggestions": suggestions,
        }

    async def bot_set_final(
        self, hash: UUID, user: UserSchema, slots: list
    ) -> MeetResponse:
        record: Meetings = await self.repository.get_meeting(hash)
        if not is_owner(record, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the organizer can set final time",
            )
        return await self.set_final(
            hash, MeetFinalUpdate(slots=slots), user
        )

