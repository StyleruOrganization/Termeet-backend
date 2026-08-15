from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from backend.src.bot_templates.parse import (
    ParseError,
    local_today,
    parse_tokens,
    timezone_offset_hours,
)
from backend.src.bot_templates.schema import BotTemplate, normalize_token
from backend.src.meetings.infrastructure import duration_to_minutes
from backend.src.meetings.schemas import MeetCreate, MeetFinalUpdate
from backend.src.users.infrastructures import Infrastructure as UsersInfra
from backend.src.users.schemas import UserSchema


def _iso_z(value: datetime) -> str:
    utc = value.astimezone(timezone.utc).replace(microsecond=0)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _local_dt(day, hhmm: str, offset: int) -> datetime:
    hours, minutes = map(int, hhmm.split(":"))
    tz = timezone(timedelta(hours=offset))
    return datetime(day.year, day.month, day.day, hours, minutes, tzinfo=tz)


def _data_range(day, start: str, end: str, offset: int) -> list[list[str]]:
    begin = _local_dt(day, start, offset)
    finish = _local_dt(day, end, offset)
    if finish <= begin:
        finish += timedelta(days=1)
    return [[_iso_z(begin), _iso_z(finish)]]


def _final_slots(day, start: str, duration: str, offset: int) -> list[list[str]]:
    minutes = duration_to_minutes(duration) or 30
    cells = max(1, minutes // 30)
    begin = _local_dt(day, start, offset).astimezone(timezone.utc)
    last = begin + timedelta(minutes=30 * (cells - 1))
    return [[_iso_z(begin), _iso_z(last)]]


def _fill(text: str, **parts: str) -> str:
    result = text or ""
    for key, value in parts.items():
        result = result.replace("{" + key + "}", value)
    return result.strip()


async def create_from_template(
    meetings,
    user: UserSchema,
    slug: str,
    tokens: list[str],
    mentions: list[dict],
    note: str | None,
):
    slug = normalize_token(slug)
    templates = [
        BotTemplate.model_validate(item)
        for item in (getattr(user, "bot_templates", None) or [])
    ]
    template = next((item for item in templates if item.slug == slug), None)
    if template is None:
        keys = ", ".join(item.slug for item in templates) or "нет"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Нет шаблона «{slug}». Ваши: {keys}",
        )

    offset = timezone_offset_hours(user.timezone)
    today = local_today(offset)
    try:
        parsed = parse_tokens(template, tokens, today)
    except ParseError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error

    day = parsed["date"]
    if day is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нужна дата",
        )

    clock = parsed["time"]
    window = parsed["window"] or (template.window_start, template.window_end)
    if clock:
        if clock < template.window_start or clock >= template.window_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Время вне окна шаблона",
            )
        start_utc = _local_dt(day, clock, offset).astimezone(timezone.utc)
        if start_utc <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Это время уже прошло",
            )

    team = None
    if template.team_mode == "pinned" and template.team_id:
        from backend.src.teams.infrastructure import Infrastructure as TeamsInfra

        team = await TeamsInfra(meetings.repository.session).get_team(
            template.team_id
        )
    elif template.team_mode == "arg":
        slug_team = parsed["team_slug"]
        if not slug_team:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нужен slug команды",
            )
        from backend.src.teams.infrastructure import Infrastructure as TeamsInfra

        team = await TeamsInfra(meetings.repository.session).get_by_slug(
            slug_team
        )
        if team is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Команда «{slug_team}» не найдена",
            )

    if team is not None:
        from backend.src.teams.services import Service as TeamService

        if not TeamService(meetings.repository.session)._can_see(team, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вас нет в этой команде",
            )

    users_infra = UsersInfra(meetings.repository.session)
    mention_ids = [
        int(item["telegram_user_id"])
        for item in mentions
        if item.get("telegram_user_id")
    ]
    mention_nicks = [
        str(item.get("username") or "").lstrip("@")
        for item in mentions
        if item.get("username")
    ]
    found = await users_infra.list_by_telegram_ids(mention_ids)
    extra = await users_infra.list_by_telegram_usernames(mention_nicks)
    by_id = {str(person.id): person for person in found}
    for person in extra:
        by_id[str(person.id)] = person
    nick_by_tid = {
        int(item["telegram_user_id"]): str(item.get("username") or "")
        for item in mentions
        if item.get("telegram_user_id")
    }
    for person in by_id.values():
        tid = person.telegram_user_id
        if tid and int(tid) in nick_by_tid:
            await users_infra.refresh_telegram_username(
                person, nick_by_tid[int(tid)]
            )
    people = [person for person in by_id.values() if str(person.id) != str(user.id)]

    missing_nicks: list[str] = []
    linked_ids = {
        int(person.telegram_user_id)
        for person in people
        if person.telegram_user_id
    }
    linked_nicks = {
        (person.telegram_username or "").lower()
        for person in people
        if person.telegram_username
    }
    for item in mentions:
        nick = str(item.get("username") or "").lstrip("@")
        tid = item.get("telegram_user_id")
        ok = False
        if tid and int(tid) in linked_ids:
            ok = True
        if nick and nick.lower() in linked_nicks:
            ok = True
        if not ok and (nick or tid):
            missing_nicks.append(f"@{nick}" if nick else str(tid))

    invited = [str(person.id) for person in people]
    date_label = day.strftime("%d.%m.%Y")
    people_label = ", ".join(
        f"{person.first_name} {person.last_name}".strip() for person in people
    )
    team_label = team.name if team else ""
    title = _fill(
        template.name,
        date=date_label,
        time=clock or "",
        people=people_label,
        team=team_label,
        note=(note or "").strip(),
    ) or template.name
    description = _fill(
        template.description,
        date=date_label,
        time=clock or "",
        people=people_label,
        team=team_label,
        note=(note or "").strip(),
    )
    payload = MeetCreate(
        name=title[:128],
        description=description[:400] or None,
        duration=template.duration,
        data_range=_data_range(day, window[0], window[1], offset),
        invited_user_ids=invited,
        team_id=team.id if team else None,
        is_closed=bool(team),
    )
    created = await meetings.create_meeting(payload, user)
    if clock:
        slots = _final_slots(day, clock, template.duration, offset)
        name = f"{user.first_name} {user.last_name}".strip() or "Организатор"
        from backend.src.meetings.schemas import SlotsUser

        await meetings.add_slots(
            created.hash,
            SlotsUser(name=name, slots=slots),
            user,
        )
        await meetings.set_final(
            created.hash, MeetFinalUpdate(slots=slots), user
        )
        created = await meetings.get_meeting(created.hash, user)
    return created, missing_nicks
