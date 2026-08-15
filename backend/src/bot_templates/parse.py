from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from backend.src.bot_templates.schema import (
    BotTemplate,
    DATE_RE,
    RANGE_RE,
    TIME_RE,
    normalize_token,
)


class ParseError(ValueError):
    pass


def timezone_offset_hours(label: str | None) -> int:
    match = re.search(r"UTC\s*([+-])\s*(\d{1,2})", label or "", re.I)
    if not match:
        return 3
    sign = 1 if match.group(1) == "+" else -1
    return sign * int(match.group(2))


def parse_clock(value: str) -> str | None:
    match = TIME_RE.fullmatch(value.strip())
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def parse_range(value: str) -> tuple[str, str] | None:
    match = RANGE_RE.fullmatch(value.strip())
    if not match:
        return None
    start = f"{int(match.group(1)):02d}:{match.group(2)}"
    end = f"{int(match.group(3)):02d}:{match.group(4)}"
    if end <= start:
        return None
    return start, end


def parse_calendar_date(value: str, today: date) -> date | None:
    match = DATE_RE.fullmatch(value.strip())
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year = today.year
    if match.group(3):
        raw = int(match.group(3))
        year = 2000 + raw if raw < 100 else raw
    try:
        parsed = date(year, month, day)
    except ValueError:
        return None
    if parsed < today:
        try:
            parsed = date(year + 1, month, day)
        except ValueError:
            return None
    return parsed


def _alias_shift(template: BotTemplate, token: str) -> int | None:
    if token in template.aliases_today:
        return 0
    if token in template.aliases_tomorrow:
        return 1
    if token in template.aliases_day_after:
        return 2
    return None


def local_today(offset_hours: int, now: datetime | None = None) -> date:
    moment = now or datetime.now(timezone.utc)
    local = moment.astimezone(timezone(timedelta(hours=offset_hours)))
    return local.date()


def parse_tokens(
    template: BotTemplate,
    tokens: list[str],
    today: date,
) -> dict:
    leftover: list[str] = []
    day: date | None = None
    clock: str | None = None
    window: tuple[str, str] | None = None

    for raw in tokens:
        token = normalize_token(raw)
        if not token:
            continue
        ranged = parse_range(raw.replace(" ", ""))
        if ranged:
            if window:
                raise ParseError("Окно часов указано дважды")
            window = ranged
            continue
        clocked = parse_clock(raw)
        if clocked:
            if clock:
                raise ParseError("Время указано дважды")
            clock = clocked
            continue
        dated = parse_calendar_date(raw, today)
        if dated:
            if day:
                raise ParseError("Дата указана дважды")
            day = dated
            continue
        shift = _alias_shift(template, token)
        if shift is not None:
            if day:
                raise ParseError("Дата указана дважды")
            day = today + timedelta(days=shift)
            continue
        leftover.append(token)

    team_slug = None
    if leftover:
        if template.team_mode != "arg":
            raise ParseError(
                f"Лишнее в команде: {' '.join(leftover)}"
            )
        if len(leftover) > 1:
            raise ParseError(
                f"Несколько slug команды: {' '.join(leftover)}"
            )
        team_slug = leftover[0]

    if template.date_mode == "off":
        if day is not None:
            raise ParseError("Этот шаблон без даты")
        day = today
    elif template.date_mode == "required" and day is None:
        if template.date_default_today:
            day = today
        else:
            raise ParseError("Нужна дата")
    elif (
        template.date_mode == "optional"
        and day is None
        and template.date_default_today
    ):
        day = today

    if template.time_mode == "off" and clock:
        raise ParseError("Этот шаблон без итогового времени")
    if template.time_mode == "required" and not clock:
        clock = template.time_default
        if not clock:
            raise ParseError("Нужно время HH:MM")
    if template.time_mode == "optional" and not clock:
        clock = template.time_default

    if window and template.time_mode == "required":
        raise ParseError("В этом шаблоне окно слотов не нужно")
    if clock and window:
        raise ParseError("Укажите либо время итога, либо окно слотов")

    return {
        "date": day,
        "time": clock,
        "window": window,
        "team_slug": team_slug,
    }
