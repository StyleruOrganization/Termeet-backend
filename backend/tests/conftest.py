import pytest_asyncio
import json

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    create_async_engine, async_sessionmaker, AsyncSession
)

from backend.src.config import config
from backend.src.models import Base
from backend.src.meetings.models import Meetings
from backend.src.users.models import Users  # noqa
from backend.src.teams.models import Teams  # noqa


PROD_DB_URL = config.prod_db.db_url


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(url=PROD_DB_URL)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture()
async def session(session_factory):
    async with session_factory() as session:
        async with session.begin():
            yield session


@pytest_asyncio.fixture()
async def load_json_data() -> dict:
    with open(
        "backend/tests/records_nologin.json",
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)
        return data


@pytest_asyncio.fixture()
async def seed_db(
        session: AsyncSession,
        load_json_data: dict
        ):

    objects: list[Meetings] = [
        Meetings(**meeting) for meeting in load_json_data["Meetings"]
        ]

    session.add_all(objects)
    await session.commit()

    yield objects

    await session.execute(delete(Meetings))
    await session.commit()
