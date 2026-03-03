from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.meetings.models import Meetings


async def test_create_all_meetings(session: AsyncSession, seed_db):
    query = select(Meetings)
    result = (await session.execute(query)).all()
    assert result


async def test_not_find_objects(session: AsyncSession):
    query = select(Meetings)
    result = (await session.execute(query)).all()
    assert not result
