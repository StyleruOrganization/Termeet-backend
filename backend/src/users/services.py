from typing import TYPE_CHECKING

from datetime import datetime

from fastapi import UploadFile

from backend.src.integrations.yandex_calendar import (
    has_calendar_scope,
    list_events,
    upsert_event,
    delete_event,
)
from backend.src.integrations.yandex_telemost import yandex_account_from_user
from backend.src.storage.photos import (
    delete_photo,
    load_photo,
    photo_key,
    read_image,
    save_photo,
)
from backend.src.users.infrastructures import Infrastructure
from backend.src.users.schemas import (
    CalendarEventCreate,
    CalendarEventItem,
    CalendarMonthResponse,
    UserSchema,
    UserSearchItem,
    UserSettingsUpdate,
)

if TYPE_CHECKING:
    from fastapi.responses import Response
    from sqlalchemy.ext.asyncio import AsyncSession
    from types_aiobotocore_s3.client import S3Client
    from uuid import UUID


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
                href=event.href,
            )
            for event in events
        ]
        return CalendarMonthResponse(events=items, has_calendar=True)

    async def create_calendar_event(
        self, user: UserSchema, payload: CalendarEventCreate
    ) -> CalendarEventItem:
        import uuid

        from fastapi import HTTPException, status

        record = await self.repository.get_with_oauth(user.id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        account = yandex_account_from_user(record)
        if not has_calendar_scope(account):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Calendar is not connected",
            )
        title = (payload.title or "").strip() or "Встреча"
        try:
            start = datetime.fromisoformat(
                payload.start.replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(payload.end.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start or end",
            )
        if end <= start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End must be after start",
            )
        uid = f"termeet-manual-{uuid.uuid4()}@termeet.tech"
        try:
            href = await upsert_event(
                account,
                uid=uid,
                summary=title,
                start=start,
                end=end,
                description=payload.description or "",
                fallback_email=record.email,
            )
        except Exception:
            href = None
        if not href:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not write to Yandex Calendar",
            )
        return CalendarEventItem(
            id=uid,
            title=title,
            start=start.isoformat(),
            end=end.isoformat(),
            href=href,
        )

    async def delete_calendar_event(self, user: UserSchema, href: str) -> None:
        from fastapi import HTTPException, status

        if not (href or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="href required",
            )
        record = await self.repository.get_with_oauth(user.id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        account = yandex_account_from_user(record)
        if not has_calendar_scope(account):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Calendar is not connected",
            )
        try:
            ok = await delete_event(
                account, href, fallback_email=record.email
            )
        except Exception:
            ok = False
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not delete from Yandex Calendar",
            )

    async def set_avatar(
        self, user: UserSchema, upload: UploadFile, s3_client
    ) -> UserSchema:
        data, content_type, ext = await read_image(upload)
        record = await self.repository.get_with_oauth(user.id)
        old_key = getattr(record, "avatar_key", None) if record else None
        key = photo_key(f"avatars/{user.id}", ext)
        await save_photo(s3_client, key, data, content_type)
        updated = await self.repository.set_avatar_key(user.id, key)
        await delete_photo(s3_client, old_key)
        return UserSchema.model_validate(updated)

    async def get_avatar(self, user_id, s3_client) -> "Response":
        from uuid import UUID

        from fastapi import HTTPException, status

        from backend.src.users.models import Users

        try:
            uid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        record = await self.repository.session.get(Users, uid)
        if record is None or not record.avatar_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Photo not found",
            )
        return await load_photo(s3_client, record.avatar_key)

