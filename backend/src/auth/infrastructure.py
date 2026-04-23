from typing import TYPE_CHECKING
from sqlalchemy import select

from backend.src.auth.repositories import Repository
from backend.src.users.models import Users
from backend.src.auth.models import OAuthAccount

if TYPE_CHECKING:
    from uuid import UUID


class Infrastructure(Repository):
    def __init__(self, session):
        super().__init__(session)

    async def register_user(self, user: dict):
        object = Users(
            first_name=user["first_name"],
            last_name=user["last_name"],
            email=user["default_email"],
            additional_emails=user["emails"]
        )
        object.oauth_accounts.append(
            OAuthAccount(
                provider="YANDEX",
                provider_user_id=int(user["id"])
            )
        )

        self.session.add(object)
        await self.session.flush()
        return object

    async def yandex_check_user_in_db(self, user: dict):
        query = select(Users, OAuthAccount).join(Users.oauth_accounts).where(
            OAuthAccount.provider_user_id == int(user["id"])
            )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def check_user_in_db(self, id: UUID):
        # Думаю, что можно сделать проверку быстрее, не доставая целый объект
        query = select(Users).where(Users.id == id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
