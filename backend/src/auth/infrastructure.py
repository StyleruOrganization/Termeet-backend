from .repositories import Repository
from backend.src.users.models import Users
from backend.src.auth.models import OAuthAccount


class Infrastructure(Repository):
    def __init__(self, session):
        super().__init__(session)

    async def register_user(self, user: dict):
        object = Users(
            first_name=user["first_name"],
            last_name=user["last_name"],
            email=user["default_email"],
            additional_email=user["emails"]
        )
        object.oauth_accounts.append(
            OAuthAccount(
                provider="YANDEX",
                provider_user_id=user["id"]
            )
        )

        self.session.add(object)
        await self.session.flush()
        await self.session.commit()
        return object
