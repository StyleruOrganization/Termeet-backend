from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy import func, select

from backend.src.auth.models import OAuthAccount, OAuthEnum
from backend.src.auth.repositories import Repository
from backend.src.auth.schemas import AuthTokens, YandexUserData
from backend.src.users.models import Users

if TYPE_CHECKING:
    from backend.src.auth.schemas import UserData
    from backend.src.users.schemas import UserSchema

class Infrastructure(Repository):
    def __init__(self, session):
        super().__init__(session)


    async def get_user_by_id(self, user_id: UUID) -> Users | None:
        user_cache = self.session.info.get("user_cache", {})
        cached_user: Users = user_cache.get(user_id)

        if cached_user:
            return cached_user

        query = (
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.id == user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def register_user(self, user: UserData) -> Users:
        object: Users = Users(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            additional_emails=user.additional_emails,
            password_hash=(
                user.password_hash if user.provider == "DEFAULT" else None
            ),
        )

        if user.provider != "DEFAULT":
            object.oauth_accounts.append(
                OAuthAccount(
                    provider=user.provider,
                    provider_user_id=int(user.provider_user_id),
                )
            )

        self.session.add(object)
        await self.session.flush()
        return object

    async def yandex_check_user_in_db(
        self, user: YandexUserData
    ) -> Users | None:
        query = (
            select(Users)
            .join(Users.oauth_accounts)
            .options(selectinload(Users.oauth_accounts))
            .where(OAuthAccount.provider_user_id == int(user.id))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def check_user_in_db_by_id(self, id: UUID) -> Users | None:
        query = (
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(Users.id == id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def check_user_in_db_by_email(self, email: str) -> Users | None:
        query = (
            select(Users)
            .options(selectinload(Users.oauth_accounts))
            .where(func.lower(Users.email) == email.lower())
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_yandex_oauth(
        self,
        user: Users,
        user_data: YandexUserData,
        tokens: AuthTokens,
        scopes: str,
        expires_at: datetime | None,
    ) -> None:
        if user.oauth_accounts is None:
            user.oauth_accounts = []
        found: OAuthAccount | None = None
        for account in list(user.oauth_accounts):
            provider = str(account.provider).upper()
            if "YANDEX" in provider:
                found = account
                break
        if not found:
            found = OAuthAccount(
                provider=OAuthEnum.YANDEX,
                provider_user_id=int(user_data.id),
            )
            user.oauth_accounts.append(found)

        found.provider_user_id = int(user_data.id)
        found.access_token = tokens.access_token
        if tokens.refresh_token:
            found.refresh_token = tokens.refresh_token
        found.scopes = tokens.scope or scopes
        found.token_expires_at = expires_at
        self.session.add(user)
        await self.session.flush()

    async def set_verify_user(self, user: UserSchema):
        user: Users = await self.get_user_by_id(user.id)

        user.is_verified = True
        await self.session.flush()
        return user
    
    async def set_new_password(self, user: UserSchema, password_hash):
        user: Users = await self.get_user_by_id(user.id)

        user.password_hash = password_hash
        await self.session.flush()
        return user