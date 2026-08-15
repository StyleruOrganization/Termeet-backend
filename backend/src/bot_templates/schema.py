from __future__ import annotations

import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RESERVED_COMMANDS = frozenset(
    {
        "start",
        "help",
        "meet",
        "meetings",
        "push",
        "next",
        "link",
        "unlink",
        "cancel",
        "about",
        "template",
        "status",
    }
)

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,15}$")
ALIAS_RE = re.compile(r"^[a-zа-я0-9_-]{1,16}$", re.IGNORECASE)
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([03]0)$")
RANGE_RE = re.compile(
    r"^([01]?\d|2[0-3]):([03]0)\s*[-–]\s*([01]?\d|2[0-3]):([03]0)$"
)
DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{2}|\d{4}))?$")
DURATIONS = ("30 мин", "1 час", "1,5 часа", "2 часа", "2,5 часа", "3 часа")
MAX_TEMPLATES = 10
MAX_ALIASES = 8


def normalize_token(value: str) -> str:
    text = (value or "").strip().lstrip("/").lower().replace("ё", "е")
    return text


def _reject_mention_shape(token: str) -> None:
    if token.startswith("@") or "@" in token:
        raise ValueError(
            "Нельзя начинать с @ — так бот отличает людей в команде"
        )


def normalize_alias_list(values: list[str] | None) -> list[str]:
    seen: list[str] = []
    for raw in values or []:
        token = normalize_token(str(raw))
        if not token or token in seen:
            continue
        seen.append(token)
    return seen


def is_clock(value: str) -> bool:
    return bool(TIME_RE.fullmatch(value.strip()))


def is_calendar_date(value: str) -> bool:
    return bool(DATE_RE.fullmatch(value.strip()))


def validate_alias_token(token: str) -> str:
    token = normalize_token(token)
    if not token:
        raise ValueError("Пустой алиас")
    _reject_mention_shape(token)
    if token in RESERVED_COMMANDS:
        raise ValueError(f"«{token}» занято командой бота")
    if not ALIAS_RE.fullmatch(token):
        raise ValueError(
            f"«{token}» не подходит: буквы, цифры, дефис или подчёркивание"
        )
    if is_clock(token) or is_calendar_date(token):
        raise ValueError(f"«{token}» похоже на время или дату, не алиас")
    return token


def validate_slug(token: str) -> str:
    token = normalize_token(token)
    _reject_mention_shape(token)
    if token in RESERVED_COMMANDS:
        raise ValueError(f"«{token}» занято командой бота")
    if not SLUG_RE.fullmatch(token):
        raise ValueError(
            "Ключ шаблона: латиница, цифры и _, с буквы, до 16 символов"
        )
    return token


def validate_team_slug(token: str) -> str:
    token = normalize_token(token)
    _reject_mention_shape(token)
    if token in RESERVED_COMMANDS:
        raise ValueError(f"«{token}» занято командой бота")
    if not ALIAS_RE.fullmatch(token):
        raise ValueError(
            "Slug команды: буквы, цифры, дефис или _, до 16 символов"
        )
    if is_clock(token) or is_calendar_date(token):
        raise ValueError("Slug не должен выглядеть как время или дата")
    return token


class BotTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    slug: str
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field("", max_length=400)
    duration: str = "30 мин"
    date_mode: Literal["off", "optional", "required"] = "required"
    date_default_today: bool = False
    aliases_today: list[str] = Field(default_factory=list)
    aliases_tomorrow: list[str] = Field(default_factory=list)
    aliases_day_after: list[str] = Field(default_factory=list)
    team_mode: Literal["off", "arg", "pinned"] = "off"
    team_id: int | None = None
    time_mode: Literal["off", "optional", "required"] = "off"
    time_default: str | None = None
    window_start: str = "09:00"
    window_end: str = "18:00"

    @field_validator("slug")
    @classmethod
    def slug_ok(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("duration")
    @classmethod
    def duration_ok(cls, value: str) -> str:
        if value not in DURATIONS:
            raise ValueError("Выберите длительность из списка")
        return value

    @field_validator(
        "aliases_today", "aliases_tomorrow", "aliases_day_after"
    )
    @classmethod
    def aliases_ok(cls, value: list[str]) -> list[str]:
        items = [validate_alias_token(item) for item in normalize_alias_list(value)]
        if len(items) > MAX_ALIASES:
            raise ValueError("Слишком много алиасов")
        return items

    @field_validator("time_default", mode="before")
    @classmethod
    def time_default_ok(cls, value):
        if value is None or value == "":
            return None
        text = str(value).strip()
        if not TIME_RE.fullmatch(text):
            raise ValueError("Время — HH:00 или HH:30")
        hours, minutes = text.split(":")
        return f"{int(hours):02d}:{minutes}"

    @field_validator("window_start", "window_end")
    @classmethod
    def window_ok(cls, value: str) -> str:
        text = (value or "").strip()
        if not TIME_RE.fullmatch(text):
            raise ValueError("Окно — HH:00 или HH:30")
        hours, minutes = text.split(":")
        return f"{int(hours):02d}:{minutes}"

    @model_validator(mode="after")
    def cross_checks(self):
        if self.team_mode == "pinned" and not self.team_id:
            raise ValueError("Выберите команду для шаблона")
        if self.team_mode != "pinned":
            self.team_id = None
        if self.time_mode == "off":
            self.time_default = None
        if self.window_end <= self.window_start:
            raise ValueError("Конец окна должен быть позже начала")
        if self.time_default and (
            self.time_default < self.window_start
            or self.time_default >= self.window_end
        ):
            raise ValueError("Время по умолчанию вне окна слотов")
        own = [
            *self.aliases_today,
            *self.aliases_tomorrow,
            *self.aliases_day_after,
        ]
        if len(own) != len(set(own)):
            raise ValueError("Один алиас указан дважды в этом шаблоне")
        if self.slug in own:
            raise ValueError(
                f"Ключ «{self.slug}» совпадает с алиасом даты в этом шаблоне"
            )
        return self


def validate_template_list(items: list | None) -> list[dict]:
    templates = [BotTemplate.model_validate(item) for item in (items or [])]
    if len(templates) > MAX_TEMPLATES:
        raise ValueError(f"Максимум {MAX_TEMPLATES} шаблонов")
    slugs: list[str] = []
    aliases: dict[str, str] = {}
    for item in templates:
        if item.slug in slugs:
            raise ValueError(f"Ключ «{item.slug}» уже есть у другого шаблона")
        slugs.append(item.slug)
        for alias in (
            item.aliases_today
            + item.aliases_tomorrow
            + item.aliases_day_after
        ):
            if alias in slugs:
                raise ValueError(
                    f"Алиас «{alias}» совпадает с ключом шаблона"
                )
            owner = aliases.get(alias)
            if owner and owner != item.slug:
                raise ValueError(
                    f"Алиас «{alias}» уже занят шаблоном «{owner}»"
                )
            aliases[alias] = item.slug
    for slug in slugs:
        if slug in aliases:
            raise ValueError(
                f"Ключ «{slug}» совпадает с алиасом даты"
            )
    return [item.model_dump() for item in templates]


def template_tokens(items: list | None) -> set[str]:
    tokens: set[str] = set()
    for raw in items or []:
        item = raw if isinstance(raw, dict) else {}
        if not isinstance(raw, dict) and hasattr(raw, "model_dump"):
            item = raw.model_dump()
        slug = normalize_token(str(item.get("slug") or ""))
        if slug:
            tokens.add(slug)
        for key in (
            "aliases_today",
            "aliases_tomorrow",
            "aliases_day_after",
        ):
            for alias in item.get(key) or []:
                token = normalize_token(str(alias))
                if token:
                    tokens.add(token)
    return tokens
