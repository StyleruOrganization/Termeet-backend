from uuid import UUID

from fastapi import HTTPException, UploadFile, status

from backend.src.storage.photos import (
    delete_photo,
    load_photo,
    photo_key,
    read_image,
    save_photo,
)
from backend.src.teams.infrastructure import Infrastructure
from backend.src.teams.models import Teams
from backend.src.teams.schemas import (
    TeamCreate,
    TeamMember,
    TeamResponse,
    TeamUpdate,
)
from backend.src.users.models import Users
from backend.src.users.schemas import UserSchema


def _member_item(user: Users) -> TeamMember:
    return TeamMember(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        has_avatar=bool(user.avatar_key),
    )


def to_response(record: Teams, current_id: UUID) -> TeamResponse:
    members = [_member_item(user) for user in (record.members or [])]
    members.sort(key=lambda item: (item.last_name, item.first_name))
    return TeamResponse(
        id=record.id,
        name=record.name,
        description=record.description or "",
        has_photo=bool(record.photo_key),
        is_owner=str(record.user_id) == str(current_id),
        members=members,
    )


class Service:
    def __init__(self, session):
        self.repository = Infrastructure(session)

    async def _owner_record(self, user: UserSchema) -> Users:
        record = await self.repository.session.get(Users, user.id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return record

    def _require_owner(self, record: Teams, user: UserSchema) -> None:
        if str(record.user_id) != str(user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the team owner can change this team",
            )

    def _can_see(self, record: Teams, user: UserSchema) -> bool:
        if str(record.user_id) == str(user.id):
            return True
        return any(str(member.id) == str(user.id) for member in record.members)

    async def _resolve_members(
        self, owner_id: UUID, member_ids: list[UUID]
    ) -> list[Users]:
        unique: list[UUID] = []
        seen: set[str] = set()
        for item in member_ids or []:
            key = str(item)
            if key == str(owner_id) or key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return await self.repository.users_by_ids(unique)

    async def list_teams(self, user: UserSchema) -> list[TeamResponse]:
        records = await self.repository.list_for_user(user.id)
        return [to_response(item, user.id) for item in records]

    async def get_team(self, team_id: int, user: UserSchema) -> TeamResponse:
        record = await self.repository.get_team(team_id)
        if not self._can_see(record, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not in this team",
            )
        return to_response(record, user.id)

    async def create_team(
        self, payload: TeamCreate, user: UserSchema
    ) -> TeamResponse:
        owner = await self._owner_record(user)
        members = await self._resolve_members(owner.id, payload.member_ids)
        record = await self.repository.create_team(owner, payload, members)
        return to_response(record, user.id)

    async def update_team(
        self, team_id: int, payload: TeamUpdate, user: UserSchema
    ) -> TeamResponse:
        record = await self.repository.get_team(team_id)
        self._require_owner(record, user)
        members = await self._resolve_members(user.id, payload.member_ids)
        updated = await self.repository.update_team(record, payload, members)
        return to_response(updated, user.id)

    async def delete_team(self, team_id: int, user: UserSchema) -> None:
        record = await self.repository.get_team(team_id)
        self._require_owner(record, user)
        await self.repository.delete_team(record)

    async def set_photo(
        self, team_id: int, user: UserSchema, upload: UploadFile, s3_client
    ) -> TeamResponse:
        record = await self.repository.get_team(team_id)
        self._require_owner(record, user)
        data, content_type, ext = await read_image(upload)
        old_key = record.photo_key
        key = photo_key(f"teams/{record.id}", ext)
        await save_photo(s3_client, key, data, content_type)
        updated = await self.repository.set_photo_key(record, key)
        await delete_photo(s3_client, old_key)
        return to_response(updated, user.id)

    async def get_photo(self, team_id: int, s3_client):
        record = await self.repository.get_team(team_id)
        return await load_photo(s3_client, record.photo_key)
