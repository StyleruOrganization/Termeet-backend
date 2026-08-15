from typing import TYPE_CHECKING

from datetime import datetime

from backend.src.integrations.yandex_calendar import (
    has_calendar_scope,
    list_events,
)
from backend.src.integrations.yandex_telemost import yandex_account_from_user
from backend.src.users.infrastructures import Infrastructure
from backend.src.users.schemas import (
    CalendarEventItem,
    CalendarMonthResponse,
    UserSchema,
    UserSearchItem,
    UserSettingsUpdate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.users.schemas import UserSchema


class Service:
    def __init__(
        self,
        session: AsyncSession = None,
    ):
        self.repository = Infrastructure(session)

    async def update_settings(
        self, user: UserSchema, payload: UserSettingsUpdate
    ) -> UserSchema:
        record = await self.repository.update_settings(user.id, payload)
        return UserSchema.model_validate(record)

    async def search_users(
        self, query: str, current: UserSchema
    ) -> list[UserSearchItem]:
        return await self.repository.search_users(query, current.id)

    async def delete_account(self, user: UserSchema) -> None:
        await self.repository.delete_account(user.id)

    async def list_calendar(
        self, user: UserSchema, start: datetime, end: datetime
    ) -> CalendarMonthResponse:
        record = await self.repository.get_with_oauth(user.id)
        if record is None:
            return CalendarMonthResponse()
        account = yandex_account_from_user(record)
        if not has_calendar_scope(account):
            return CalendarMonthResponse(has_calendar=False)
        try:
            events = await list_events(
                account, start, end, fallback_email=record.email
            )
        except Exception:
            return CalendarMonthResponse(
                has_calendar=True,
                error="calendar_unavailable",
            )
        items = [
            CalendarEventItem(
                id=event.uid,
                title=event.title,
                start=event.start.isoformat(),
                end=event.end.isoformat(),
            )
            for event in events
        ]
        return CalendarMonthResponse(events=items, has_calendar=True)

