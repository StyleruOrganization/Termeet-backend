from typing import TYPE_CHECKING
from sqlalchemy import select

from backend.src.auth.repositories import Repository
from backend.src.auth.schemas import YandexUserData
from backend.src.users.models import Users
from backend.src.auth.models import OAuthAccount

if TYPE_CHECKING:
    from uuid import UUID
    from backend.src.auth.schemas import UserData
    from backend.src.users.schemas import UserSchema

class Infrastructure(Repository):
    def __init__(self, session):
        super().__init__(session)

    async def get_cached_user(self, user: UserSchema) -> Users | None:
        user_cache = self.session.info.get("user_cache", {})
        cached_user: Users = user_cache.get(user.id)

        return cached_user
    
    async def get_user_by_id(self, user_id: UUID) -> Users | None:
        return await self.session.get(Users, user_id)

    async def register_user(self, user: UserData) -> Users:
        object: Users = Users(
            **user.model_dump(
                include={
                    "first_name",
                    "last_name",
                    "email",
                    "additional_emails",
                }
            )
        )

        if user.provider == "DEFAULT":
            object.password_hash = user.password_hash
        else:
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
            select(Users, OAuthAccount)
            .join(Users.oauth_accounts)
            .where(OAuthAccount.provider_user_id == int(user.id))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def check_user_in_db_by_id(self, id: UUID) -> Users | None:
        return await self.session.get(Users, id)

    async def check_user_in_db_by_email(self, email: str) -> Users | None:
        query = select(Users).where(Users.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def set_verify_user(self, user: UserSchema):
        user_cache = (await self.get_cached_user(user))

        if user_cache:
            user = user_cache
        else:
            user = await self.get_user_by_id(user.id)

        user.is_verified = True
        await self.session.flush()
        return user