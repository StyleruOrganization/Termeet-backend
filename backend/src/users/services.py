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
    TelegramConfirmIn,
    TelegramConfirmOut,
    TelegramLinkResponse,
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

    async def start_telegram_link(
        self, user: UserSchema
    ) -> TelegramLinkResponse:
        from datetime import datetime, timedelta, timezone
        import secrets

        from fastapi import HTTPException, status

        from backend.src.config import config

        username = (config.telegram_bot.USERNAME or "").lstrip("@").strip()
        if not username or not config.telegram_bot.SECRET:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram bot is not configured",
            )
        token = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        await self.repository.set_telegram_link_token(
            user.id, token, expires
        )
        return TelegramLinkResponse(
            url=f"https://t.me/{username}?start=link_{token}",
            bot_username=username,
        )

    async def unlink_telegram_for_user(self, user: UserSchema) -> UserSchema:
        from fastapi import HTTPException, status

        record = await self.repository.get_with_oauth(user.id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        updated = await self.repository.clear_telegram(record)
        return UserSchema.model_validate(updated)

    async def confirm_telegram_link(
        self, payload: TelegramConfirmIn
    ) -> TelegramConfirmOut:
        from datetime import datetime, timezone

        from fastapi import HTTPException, status

        token = (payload.token or "").strip()
        record = await self.repository.get_by_link_token(token)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired link token",
            )
        expires = record.telegram_link_expires
        if expires is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired link token",
            )
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired link token",
            )

        already = await self.repository.get_by_telegram_id(
            payload.telegram_user_id
        )
        if already is not None and already.id != record.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Telegram is already linked to another account",
            )

        already_linked = (
            record.telegram_user_id == payload.telegram_user_id
        )
        nick = (payload.telegram_username or "").lstrip("@").strip()
        nick = nick[:32] or None
        updated = await self.repository.bind_telegram(
            record, payload.telegram_user_id, nick
        )
        return TelegramConfirmOut(
            ok=True,
            first_name=updated.first_name,
            already_linked=already_linked,
        )

    async def unlink_telegram_by_id(self, telegram_user_id: int) -> None:
        from fastapi import HTTPException, status

        record = await self.repository.get_by_telegram_id(telegram_user_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Telegram is not linked",
            )
        await self.repository.clear_telegram(record)

    async def user_by_telegram_id(self, telegram_user_id: int) -> UserSchema:
        from fastapi import HTTPException, status

        record = await self.repository.get_by_telegram_id(telegram_user_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Telegram is not linked",
            )
        return UserSchema.model_validate(record)

