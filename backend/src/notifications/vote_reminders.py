import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.src.database import async_session_maker
from backend.src.meetings.models import Meetings
from backend.src.notifications.meet_emails import MSK, notify_vote_nudge
from backend.src.teams.models import Teams
from backend.src.users.models import Users

logger = logging.getLogger(__name__)

POLL_SECONDS = 60
LATE_WINDOW = timedelta(minutes=90)


def _as_uuid(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _voted_user_ids(meeting: Meetings) -> set[str]:
    return {
        str(item.get("user_id"))
        for item in (meeting.slots or [])
        if isinstance(item, dict) and item.get("user_id")
    }


def _observer_ids(meeting: Meetings) -> set[str]:
    return {
        str(item.get("user_id"))
        for item in (meeting.observers or [])
        if isinstance(item, dict) and item.get("user_id")
    }


def _candidate_ids(meeting: Meetings) -> set[str]:
    ids = {
        str(item) for item in (meeting.invited_user_ids or []) if item
    }
    team = meeting.team
    if team is not None:
        ids.add(str(team.user_id))
        for member in team.members or []:
            ids.add(str(member.id))
    skip = _voted_user_ids(meeting) | _observer_ids(meeting)
    if meeting.owner_id:
        skip.add(str(meeting.owner_id))
    return ids - skip


async def _emails_for_nudge(session, meeting: Meetings) -> list[str]:
    ids = [_as_uuid(item) for item in _candidate_ids(meeting)]
    uuids = [item for item in ids if item is not None]
    if not uuids:
        return []
    result = await session.execute(select(Users).where(Users.id.in_(uuids)))
    emails: list[str] = []
    for user in result.scalars():
        if user.email:
            emails.append(user.email)
    return emails


def _due_offsets(meeting: Meetings, now: datetime) -> list[int]:
    deadline = _aware(meeting.vote_deadline)
    if now >= deadline:
        return []
    sent = {int(item) for item in (meeting.remind_sent or [])}
    due: list[int] = []
    for raw in meeting.remind_offsets or []:
        try:
            offset = int(raw)
        except (TypeError, ValueError):
            continue
        if offset in sent:
            continue
        send_at = deadline - timedelta(minutes=offset)
        if send_at <= now < deadline and now - send_at <= LATE_WINDOW:
            due.append(offset)
    return due


async def process_due_reminders() -> None:
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Meetings)
            .options(
                selectinload(Meetings.owner),
                selectinload(Meetings.team).selectinload(Teams.members),
            )
            .where(
                Meetings.remind_enabled.is_(True),
                Meetings.vote_deadline.is_not(None),
                Meetings.vote_deadline > now,
            )
        )
        meetings = list(result.scalars().unique())
        for meeting in meetings:
            if meeting.final_slot:
                continue
            due = _due_offsets(meeting, now)
            if not due:
                continue
            emails = await _emails_for_nudge(session, meeting)
            deadline_text = (
                _aware(meeting.vote_deadline)
                .astimezone(MSK)
                .strftime("%d.%m.%Y %H:%M (МСК)")
            )
            if emails:
                await notify_vote_nudge(
                    emails,
                    meeting.name,
                    meeting.id,
                    deadline_text,
                )
            sent = [int(item) for item in (meeting.remind_sent or [])]
            for offset in due:
                if offset not in sent:
                    sent.append(offset)
            meeting.remind_sent = sent
            session.add(meeting)
            logger.info(
                "vote nudge sent meet=%s offsets=%s recipients=%s",
                meeting.id,
                due,
                len(emails),
            )
        await session.commit()


async def run_vote_reminder_loop() -> None:
    while True:
        try:
            await process_due_reminders()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("vote reminders tick failed")
        await asyncio.sleep(POLL_SECONDS)
