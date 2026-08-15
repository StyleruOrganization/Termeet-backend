from html import escape
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.src.database import async_session_maker
from backend.src.meetings.models import Meetings
from backend.src.notifications.meet_emails import (
    MSK,
    meet_url,
    notify_vote_nudge,
)
from backend.src.notifications.telegram import send_telegram_message
from backend.src.teams.models import Teams
from backend.src.users.models import Users

logger = logging.getLogger(__name__)

POLL_SECONDS = 60
LATE_WINDOW = timedelta(minutes=90)
FINAL_REMIND_OFFSETS = (1440, 60)


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
        if user.email and getattr(user, "notify_email", True):
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
            await _telegram_vote_nudge(
                session, meeting, deadline_text
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


def _final_start(meeting: Meetings) -> datetime | None:
    final = meeting.final_slot
    if not isinstance(final, list) or not final:
        return None
    first = final[0]
    if not isinstance(first, list) or not first:
        return None
    try:
        parsed = datetime.fromisoformat(
            str(first[0]).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    return _aware(parsed)


def _final_due_offsets(meeting: Meetings, now: datetime) -> list[int]:
    start = _final_start(meeting)
    if start is None or now >= start:
        return []
    sent = {str(item) for item in (meeting.final_remind_sent or [])}
    due: list[int] = []
    for offset in FINAL_REMIND_OFFSETS:
        if str(offset) in sent:
            continue
        send_at = start - timedelta(minutes=offset)
        if send_at <= now < start and now - send_at <= LATE_WINDOW:
            due.append(offset)
    return due


def _final_recipient_ids(meeting: Meetings) -> set[str]:
    ids: set[str] = set()
    if meeting.owner_id:
        ids.add(str(meeting.owner_id))
    for item in meeting.invited_user_ids or []:
        if item:
            ids.add(str(item))
    team = meeting.team
    if team is not None:
        ids.add(str(team.user_id))
        for member in team.members or []:
            ids.add(str(member.id))
    for item in meeting.slots or []:
        if isinstance(item, dict) and item.get("user_id"):
            ids.add(str(item["user_id"]))
    return ids - _observer_ids(meeting)


async def _telegram_vote_nudge(
    session, meeting: Meetings, deadline_text: str
) -> None:
    ids = [_as_uuid(item) for item in _candidate_ids(meeting)]
    uuids = [item for item in ids if item is not None]
    if not uuids:
        return
    result = await session.execute(select(Users).where(Users.id.in_(uuids)))
    title = escape(meeting.name or "Встреча")
    text = (
        f"Напоминание: отметьте время на «{title}».\n"
        f"Срок: {deadline_text}\n"
        f"{meet_url(meeting.id)}"
    )
    for user in result.scalars():
        if not getattr(user, "notify_telegram", True):
            continue
        if user.telegram_user_id:
            await send_telegram_message(int(user.telegram_user_id), text)


async def _telegram_final_nudge(
    session, meeting: Meetings, offset: int
) -> None:
    ids = [_as_uuid(item) for item in _final_recipient_ids(meeting)]
    uuids = [item for item in ids if item is not None]
    if not uuids:
        return
    start = _final_start(meeting)
    when = (
        start.astimezone(MSK).strftime("%d.%m.%Y %H:%M (МСК)")
        if start
        else ""
    )
    if offset >= 1440:
        when_label = "завтра"
    else:
        when_label = "через час"
    title = escape(meeting.name or "Встреча")
    text = (
        f"Встреча «{title}» {when_label}.\n"
        f"{when}\n"
        f"{meet_url(meeting.id)}"
    )
    result = await session.execute(select(Users).where(Users.id.in_(uuids)))
    for user in result.scalars():
        if not getattr(user, "notify_telegram", True):
            continue
        if user.telegram_user_id:
            await send_telegram_message(int(user.telegram_user_id), text)


async def process_final_reminders() -> None:
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Meetings)
            .options(
                selectinload(Meetings.team).selectinload(Teams.members),
            )
            .where(Meetings.final_slot.is_not(None))
        )
        meetings = list(result.scalars().unique())
        for meeting in meetings:
            due = _final_due_offsets(meeting, now)
            if not due:
                continue
            for offset in due:
                await _telegram_final_nudge(session, meeting, offset)
            sent = [str(item) for item in (meeting.final_remind_sent or [])]
            for offset in due:
                if str(offset) not in sent:
                    sent.append(str(offset))
            meeting.final_remind_sent = sent
            session.add(meeting)
            logger.info(
                "final remind sent meet=%s offsets=%s",
                meeting.id,
                due,
            )
        await session.commit()


async def run_vote_reminder_loop() -> None:
    while True:
        try:
            await process_due_reminders()
            await process_final_reminders()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("vote reminders tick failed")
        await asyncio.sleep(POLL_SECONDS)
