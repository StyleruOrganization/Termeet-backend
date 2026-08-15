from fastapi import HTTPException, status

from sqlalchemy.orm import selectinload
from sqlalchemy import delete, or_, select, update

from backend.src.auth.models import OAuthAccount
from backend.src.feedback.models import Feedback
from backend.src.meetings.models import Meetings, MeetingsUsers
from backend.src.teams.models import Teams, TeamsUsers
from backend.src.users.models import Users
from backend.src.users.repositories import Repository
from backend.src.users.schemas import UserSearchItem, UserSettingsUpdate


class Infrastructure(Repository):
    def __init__(self, session):
        super().__init__(session)

    async def get_with_oauth(self, user_id) -> Users | None:
        result = await self.session.execute(
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_settings(
        self, user_id, payload: UserSettingsUpdate
    ) -> Users:
        record: Users | None = await self.session.get(Users, user_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        data = payload.model_dump(exclude_unset=True)
        if "first_name" in data and data["first_name"] is not None:
            record.first_name = data["first_name"]
        if "last_name" in data and data["last_name"] is not None:
            record.last_name = data["last_name"]
        if "timezone" in data and data["timezone"] is not None:
            record.timezone = data["timezone"]
        if "theme" in data and data["theme"] is not None:
            record.theme = data["theme"]
        if "suggest_prefill" in data and data["suggest_prefill"] is not None:
            record.suggest_prefill = data["suggest_prefill"]
        if "locale" in data and data["locale"] is not None:
            record.locale = data["locale"]
        if "grid_window_start" in data and data["grid_window_start"]:
            record.grid_window_start = data["grid_window_start"]
        if "grid_window_end" in data and data["grid_window_end"]:
            record.grid_window_end = data["grid_window_end"]
        if "availability_template" in data:
            template = data["availability_template"] or []
            record.availability_template = [
                item
                if isinstance(item, dict)
                else item.model_dump()
                for item in template
            ]
        if "notify_on_vote" in data and data["notify_on_vote"] is not None:
            record.notify_on_vote = data["notify_on_vote"]
        if "notify_on_final" in data and data["notify_on_final"] is not None:
            record.notify_on_final = data["notify_on_final"]
        if "show_onboarding" in data and data["show_onboarding"] is not None:
            record.show_onboarding = data["show_onboarding"]
        if "contact_email" in data:
            record.contact_email = data["contact_email"]
        if "contact_telegram" in data:
            record.contact_telegram = data["contact_telegram"]
        if "contact_vk" in data:
            record.contact_vk = data["contact_vk"]

        self.session.add(record)
        await self.session.flush()
        loaded = await self.session.execute(
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.id == user_id)
        )
        return loaded.scalar_one()

    async def set_avatar_key(self, user_id, key: str | None) -> Users:
        record: Users | None = await self.session.get(Users, user_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        record.avatar_key = key
        self.session.add(record)
        await self.session.flush()
        loaded = await self.session.execute(
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.id == user_id)
        )
        return loaded.scalar_one()

    async def search_users(self, query: str, current_id) -> list[UserSearchItem]:
        needle = (query or "").strip()
        if len(needle) < 2:
            return []

        pattern = f"%{needle}%"
        result = await self.session.execute(
            select(Users)
            .where(Users.is_active.is_(True))
            .where(Users.id != current_id)
            .where(
                or_(
                    Users.first_name.ilike(pattern),
                    Users.last_name.ilike(pattern),
                    Users.email.ilike(pattern),
                )
            )
            .limit(8)
        )
        return [
            UserSearchItem(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                has_avatar=bool(user.avatar_key),
            )
            for user in result.scalars().all()
        ]

    async def delete_account(self, user_id) -> None:
        record: Users | None = await self.session.get(Users, user_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        owned = (
            await self.session.execute(
                select(Meetings).where(Meetings.owner_id == user_id)
            )
        ).scalars().all()
        owned_ids = [meeting.id for meeting in owned]
        if owned_ids:
            await self.session.execute(
                delete(MeetingsUsers).where(
                    MeetingsUsers.meeting_id.in_(owned_ids)
                )
            )
            for meeting in owned:
                await self.session.delete(meeting)

        await self.session.execute(
            delete(MeetingsUsers).where(MeetingsUsers.user_id == user_id)
        )
        await self.session.execute(
            delete(OAuthAccount).where(OAuthAccount.user_id == user_id)
        )
        await self.session.execute(
            update(Feedback)
            .where(Feedback.user_id == user_id)
            .values(user_id=None)
        )

        teams = (
            await self.session.execute(
                select(Teams).where(Teams.user_id == user_id)
            )
        ).scalars().all()
        team_ids = [team.id for team in teams]
        if team_ids:
            await self.session.execute(
                update(Meetings)
                .where(Meetings.team_id.in_(team_ids))
                .values(team_id=None)
            )
            await self.session.execute(
                delete(TeamsUsers).where(TeamsUsers.team_id.in_(team_ids))
            )
            for team in teams:
                await self.session.delete(team)

        await self.session.execute(
            delete(TeamsUsers).where(TeamsUsers.user_id == user_id)
        )

        await self.session.delete(record)
        await self.session.flush()

    async def set_telegram_link_token(
        self, user_id, token: str, expires
    ) -> None:
        record: Users | None = await self.session.get(Users, user_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        record.telegram_link_token = token
        record.telegram_link_expires = expires
        self.session.add(record)
        await self.session.flush()

    async def get_by_link_token(self, token: str) -> Users | None:
        result = await self.session.execute(
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.telegram_link_token == token)
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_user_id: int) -> Users | None:
        result = await self.session.execute(
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()

    async def bind_telegram(
        self,
        record: Users,
        telegram_user_id: int,
        telegram_username: str | None,
    ) -> Users:
        record.telegram_user_id = telegram_user_id
        record.telegram_username = telegram_username
        record.telegram_link_token = None
        record.telegram_link_expires = None
        self.session.add(record)
        await self.session.flush()
        loaded = await self.session.execute(
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.id == record.id)
        )
        return loaded.scalar_one()

    async def clear_telegram(self, record: Users) -> Users:
        record.telegram_user_id = None
        record.telegram_username = None
        record.telegram_link_token = None
        record.telegram_link_expires = None
        self.session.add(record)
        await self.session.flush()
        loaded = await self.session.execute(
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.id == record.id)
        )
        return loaded.scalar_one()
