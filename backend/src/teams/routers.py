from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3.client import S3Client

from backend.src.auth.dependencies import get_required_active_user
from backend.src.dependencies import get_async_session, get_s3_client
from backend.src.teams.schemas import TeamCreate, TeamResponse, TeamUpdate
from backend.src.teams.services import Service
from backend.src.users.schemas import UserSchema


router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=list[TeamResponse], summary="Мои команды")
async def list_teams(
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await Service(session).list_teams(user)


@router.post(
    "",
    response_model=TeamResponse,
    status_code=201,
    summary="Создать команду",
)
async def create_team(
    payload: TeamCreate,
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await Service(session).create_team(payload, user)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: int,
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await Service(session).get_team(team_id, user)


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    payload: TeamUpdate,
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await Service(session).update_team(team_id, payload, user)


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_id: int,
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    await Service(session).delete_team(team_id, user)


@router.post("/{team_id}/photo", response_model=TeamResponse)
async def upload_team_photo(
    team_id: int,
    file: UploadFile = File(...),
    user: UserSchema = Depends(get_required_active_user),
    session: AsyncSession = Depends(get_async_session),
    s3_client: S3Client = Depends(get_s3_client),
):
    return await Service(session).set_photo(team_id, user, file, s3_client)


@router.get("/{team_id}/photo")
async def team_photo(
    team_id: int,
    session: AsyncSession = Depends(get_async_session),
    s3_client: S3Client = Depends(get_s3_client),
):
    return await Service(session).get_photo(team_id, s3_client)
