from fastapi import HTTPException, status

from sqlalchemy import or_, select

from backend.src.users.models import Users
from backend.src.users.repositories import Repository
from backend.src.users.schemas import UserSearchItem, UserSettingsUpdate


class Infrastructure(Repository):
    def __init__(self, session):
        super().__init__(session)

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
        if "timezone" in data and data["timezone"] is not None:
            record.timezone = data["timezone"]
        if "theme" in data and data["theme"] is not None:
            record.theme = data["theme"]
        if "suggest_prefill" in data and data["suggest_prefill"] is not None:
            record.suggest_prefill = data["suggest_prefill"]
        if "availability_template" in data:
            template = data["availability_template"] or []
            record.availability_template = [
                item
                if isinstance(item, dict)
                else item.model_dump()
                for item in template
            ]

        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

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
            )
            for user in result.scalars().all()
        ]
