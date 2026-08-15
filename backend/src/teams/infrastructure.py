from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.src.teams.models import Teams
from backend.src.teams.repositories import Repository
from backend.src.teams.schemas import TeamCreate, TeamUpdate
from backend.src.users.models import Users


class Infrastructure(Repository):
    def __init__(self, session):
        super().__init__(session)

    def _query(self):
        return select(Teams).options(
            selectinload(Teams.members),
            selectinload(Teams.user),
        )

    async def list_for_user(self, user_id: UUID) -> list[Teams]:
        owned = await self.session.execute(
            self._query().where(Teams.user_id == user_id)
        )
        member = await self.session.execute(
            self._query().join(Teams.members).where(Users.id == user_id)
        )
        items: dict[int, Teams] = {}
        for team in list(owned.scalars().unique().all()) + list(
            member.scalars().unique().all()
        ):
            items[team.id] = team
        return sorted(items.values(), key=lambda team: team.id, reverse=True)

    async def get_team(self, team_id: int) -> Teams:
        result = await self.session.execute(
            self._query().where(Teams.id == team_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found",
            )
        return record

    async def get_by_slug(self, slug: str) -> Teams | None:
        result = await self.session.execute(
            self._query().where(Teams.slug == slug)
        )
        return result.scalar_one_or_none()

    async def users_by_ids(self, ids: list[UUID]) -> list[Users]:
        if not ids:
            return []
        result = await self.session.execute(
            select(Users).where(Users.id.in_(ids), Users.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def create_team(
        self, owner: Users, payload: TeamCreate, members: list[Users]
    ) -> Teams:
        record = Teams(
            name=payload.name,
            slug=payload.slug,
            description=payload.description or "",
            user_id=owner.id,
        )
        record.members = members
        self.session.add(record)
        await self.session.flush()
        return await self.get_team(record.id)

    async def update_team(
        self, record: Teams, payload: TeamUpdate, members: list[Users]
    ) -> Teams:
        record.name = payload.name
        record.slug = payload.slug
        record.description = payload.description or ""
        record.members = members
        self.session.add(record)
        await self.session.flush()
        return await self.get_team(record.id)

    async def delete_team(self, record: Teams) -> None:
        from sqlalchemy import update

        from backend.src.meetings.models import Meetings

        await self.session.execute(
            update(Meetings)
            .where(Meetings.team_id == record.id)
            .values(team_id=None)
        )
        await self.session.delete(record)
        await self.session.flush()

    async def set_photo_key(self, record: Teams, key: str | None) -> Teams:
        record.photo_key = key
        self.session.add(record)
        await self.session.flush()
        return await self.get_team(record.id)
