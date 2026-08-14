from typing import TYPE_CHECKING

from backend.src.users.infrastructures import Infrastructure
from backend.src.users.schemas import UserSchema, UserSearchItem, UserSettingsUpdate

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

