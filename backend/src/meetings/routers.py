from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.dependencies import get_async_session
from .schemas import MeetCreate, MeetResponse, SlotsUser
from .services import Service


router = APIRouter(prefix="/meet", tags=["Meet"])


@router.get("/{hash}",
            response_model=MeetResponse,
            summary="",
            description=""
            )
async def get_meeting(
    hash: UUID,
    session: AsyncSession = Depends(get_async_session)
) -> MeetResponse:
    service = Service(session)
    return await service.get_meeting(hash)


# В случае чего добавь статус код 201
@router.post("/create",
             response_model=MeetResponse,
             summary="",
             description=""
             )
async def create_meeting(
    meeting: MeetCreate,
    session: AsyncSession = Depends(get_async_session)
) -> MeetResponse:
    service = Service(session)
    return await service.create_meeting(meeting)


# Измени потом на patch
@router.patch("/{hash}/slots",
              response_model=SlotsUser,
              summary="fdsa",
              description="asdf")
async def add_slots(
    hash: UUID,
    slots: SlotsUser,
    session: AsyncSession = Depends(get_async_session)
):
    service = Service(session)
    return await service.add_slots(hash, slots)
