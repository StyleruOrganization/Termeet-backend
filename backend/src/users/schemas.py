from uuid import UUID
from typing import Literal, Optional
import re

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


_TELEGRAM_USER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
_VK_ID = re.compile(r"^id\d{1,12}$", re.I)
_VK_SCREEN = re.compile(r"^[A-Za-z][A-Za-z0-9._]{2,31}$")
_VK_DIGITS = re.compile(r"^\d{1,12}$")
_TELEGRAM_PREFIX = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me)/", re.I
)
_VK_PREFIX = re.compile(r"^(?:https?://)?(?:m\.)?vk\.com/", re.I)


def _normalize_telegram(value: str) -> str:
    nick = _TELEGRAM_PREFIX.sub("", value.strip())
    nick = nick.lstrip("@").rstrip("/")
    nick = nick.split("?", 1)[0]
    if not _TELEGRAM_USER.fullmatch(nick):
        raise ValueError("Укажите Telegram как @username или t.me/username")
    return f"@{nick}"


def _normalize_vk(value: str) -> str:
    slug = _VK_PREFIX.sub("", value.strip())
    slug = slug.lstrip("@").rstrip("/")
    slug = slug.split("?", 1)[0].split("/", 1)[0]
    if _VK_DIGITS.fullmatch(slug):
        return f"id{slug}"
    if _VK_ID.fullmatch(slug) or _VK_SCREEN.fullmatch(slug):
        return slug
    raise ValueError("Укажите страницу ВК: vk.com/имя, id123 или короткое имя")


class AvailabilityInterval(BaseModel):
    weekday: int | None = Field(None, ge=1, le=7)
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")

    @field_validator("start")
    @classmethod
    def valid_start(cls, value: str) -> str:
        hours, minutes = value.split(":")
        if int(hours) > 23 or minutes not in ("00", "30"):
            raise ValueError("start must be HH:00 or HH:30")
        return value

    @field_validator("end")
    @classmethod
    def valid_end(cls, value: str, info) -> str:
        hours, minutes = value.split(":")
        is_midnight = value == "24:00"
        if not is_midnight and (
            int(hours) > 23 or minutes not in ("00", "30")
        ):
            raise ValueError("end must be HH:00, HH:30 or 24:00")
        start = info.data.get("start")
        if start and value <= start:
            raise ValueError("end must be later than start")
        return value


class UserSchema(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    nickname: Optional[str]
    is_active: bool
    is_verified: bool
    email: str
    additional_emails: Optional[list]
    timezone: str = "UTC +3:00 (Москва)"
    theme: str = "light"
    suggest_prefill: bool = True
    availability_template: list[AvailabilityInterval] = Field(
        default_factory=list
    )
    locale: str = "ru"
    grid_window_start: str = "10 : 00"
    grid_window_end: str = "19 : 00"
    notify_on_vote: bool = True
    notify_on_final: bool = True
    show_onboarding: bool = True
    has_yandex: bool = False
    has_telemost: bool = False
    has_calendar: bool = False
    has_avatar: bool = False
    yandex_login: str | None = None
    yandex_email: str | None = None
    yandex_name: str | None = None
    contact_email: str | None = None
    contact_telegram: str | None = None
    contact_vk: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def from_orm_without_computed_nickname(cls, data):
        if not hasattr(data, "__table__"):
            return data
        payload = {
            "id": data.id,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "nickname": data.first_name,
            "is_active": data.is_active,
            "is_verified": data.is_verified,
            "email": data.email,
            "additional_emails": data.additional_emails,
            "timezone": getattr(data, "timezone", "UTC +3:00 (Москва)"),
            "theme": getattr(data, "theme", "light"),
            "suggest_prefill": getattr(data, "suggest_prefill", True),
            "availability_template": getattr(
                data, "availability_template", []
            )
            or [],
            "locale": getattr(data, "locale", "ru") or "ru",
            "grid_window_start": getattr(
                data, "grid_window_start", "10 : 00"
            )
            or "10 : 00",
            "grid_window_end": getattr(
                data, "grid_window_end", "19 : 00"
            )
            or "19 : 00",
            "notify_on_vote": getattr(data, "notify_on_vote", True),
            "notify_on_final": getattr(data, "notify_on_final", True),
            "show_onboarding": getattr(data, "show_onboarding", True),
            "has_avatar": bool(getattr(data, "avatar_key", None)),
            "has_yandex": False,
            "has_telemost": False,
            "has_calendar": False,
            "yandex_login": None,
            "yandex_email": None,
            "yandex_name": None,
            "contact_email": getattr(data, "contact_email", None),
            "contact_telegram": getattr(data, "contact_telegram", None),
            "contact_vk": getattr(data, "contact_vk", None),
        }
        from backend.src.integrations.yandex_calendar import has_calendar_scope
        from backend.src.integrations.yandex_telemost import (
            has_telemost_scope,
            yandex_account_from_user,
        )

        yandex = yandex_account_from_user(data)
        payload["has_yandex"] = bool(yandex)
        payload["has_telemost"] = has_telemost_scope(yandex)
        payload["has_calendar"] = has_calendar_scope(yandex)
        if yandex:
            payload["yandex_login"] = getattr(yandex, "yandex_login", None)
            payload["yandex_email"] = getattr(yandex, "yandex_email", None)
            payload["yandex_name"] = getattr(yandex, "display_name", None)
        return payload


class UserSettingsUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    timezone: str | None = Field(None, max_length=64)
    theme: Literal["light", "dark"] | None = None
    suggest_prefill: bool | None = None
    availability_template: list[AvailabilityInterval] | None = None
    locale: Literal["ru", "en", "de"] | None = None
    grid_window_start: str | None = Field(None, max_length=16)
    grid_window_end: str | None = Field(None, max_length=16)
    notify_on_vote: bool | None = None
    notify_on_final: bool | None = None
    show_onboarding: bool | None = None
    contact_email: EmailStr | None = Field(None, max_length=256)
    contact_telegram: str | None = Field(None, max_length=128)
    contact_vk: str | None = Field(None, max_length=256)

    model_config = ConfigDict(extra="ignore")

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator(
        "contact_email", "contact_telegram", "contact_vk", mode="before"
    )
    @classmethod
    def strip_contact(cls, value):
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value

    @field_validator("contact_telegram")
    @classmethod
    def valid_telegram(cls, value):
        if value is None:
            return None
        return _normalize_telegram(value)

    @field_validator("contact_vk")
    @classmethod
    def valid_vk(cls, value):
        if value is None:
            return None
        return _normalize_vk(value)

    @field_validator("availability_template")
    @classmethod
    def limit_template(cls, value):
        if value is not None and len(value) > 200:
            raise ValueError("Слишком много интервалов в шаблоне")
        return value


class UserSearchItem(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    has_avatar: bool = False


class CalendarEventItem(BaseModel):
    id: str
    title: str
    start: str
    end: str
    href: str = ""
    source: Literal["yandex"] = "yandex"


class CalendarEventCreate(BaseModel):
    title: str
    start: str
    end: str
    description: str | None = None


class CalendarMonthResponse(BaseModel):
    events: list[CalendarEventItem] = Field(default_factory=list)
    has_calendar: bool = False
    error: str | None = None

