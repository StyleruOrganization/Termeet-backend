import pytest

from sqlalchemy import inspect, text, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import (
    create_async_engine, async_sessionmaker, AsyncSession
)

from backend.src.config import config
from backend.src.models import Base
from backend.src.meetings.models import Meetings  # noqa
from backend.src.users.models import Users  # noqa
from backend.src.teams.models import Teams  # noqa


TEST_DB_URL = config.test_db.db_url


async def test_link_to_db():
    engine = create_async_engine(url=TEST_DB_URL)
    try:
        async with engine.connect() as con:
            await con.execute(text("SELECT 1"))
    except ConnectionRefusedError:
        assert False, "Не удалось установить соедение с БД"
    assert True


@pytest.fixture()
async def engine():
    engine = create_async_engine(url=TEST_DB_URL)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture()
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture()
async def session(session_factory):
    async with session_factory() as session:
        yield session


def inspector_get_table_names(conn):
    inspector = inspect(conn)
    print(inspector.get_view_names())
    return inspector.get_table_names()


async def test_create_tables(engine):
    need_tables = [
        "users",
        "meetings",
        "teams",
        "meetings_users"
    ]

    async with engine.connect() as conn:
        tables = await conn.run_sync(inspector_get_table_names)

    for table in need_tables:
        assert table in tables


async def test_create_object_meetings(session: AsyncSession):
    meetings = [
        Meetings(
            name="Встреча 1",
            description="Крутая встреча",
            link="https://telemost",
            duration="01:30",
            data_range=[
                [
                    "2026-12-21Т22:00:00Z",
                    "2026-12-22Т02:00:00Z"
                ],
                [
                    "2026-12-22Т22:00:00Z",
                    "2026-12-23Т02:00:00Z"
                ],
                [
                    "2026-12-24Т22:00:00Z",
                    "2026-12-25Т02:00:00Z"
                ]
            ]),
        Meetings(
            name="Встреча 2",
            description="Очень крутая встреча",
            link="https://telemost",
            duration="01:00",
            data_range=[
                [
                    "2026-12-21Т22:00:00Z",
                    "2026-12-22Т02:00:00Z"
                ],
                [
                    "2026-12-22Т22:00:00Z",
                    "2026-12-23Т02:00:00Z"
                ],
                [
                    "2026-12-24Т22:00:00Z",
                    "2026-12-25Т02:00:00Z"
                ]
            ],
            slots={
                "Данек": [
                    [
                        "2026-12-21Т22:00:00Z",
                        "2026-12-22Т02:00:00Z"
                    ],
                    [
                        "2026-12-22Т22:00:00Z",
                        "2026-12-23Т02:00:00Z"
                    ]
                    ],
                "Кирилл": [
                    [
                        "2026-12-21Т22:00:00Z",
                        "2026-12-21Т23:00:00Z"
                    ],
                    [
                        "2026-12-23Т00:00:00Z",
                        "2026-12-23Т01:00:00Z"
                    ]
                    ],
                "Колян": [
                    [
                        "2026-12-25Т00:00:00Z",
                        "2026-12-25Т00:00:00Z"
                    ]
                ]
            }),
    ]

    session.add_all(meetings)
    await session.commit()

    print(f"Созданы встречи с hash: {[meeting.id for meeting in meetings]}")
    print(
        f"Созданы встречи с slots: {[meeting.slots for meeting in meetings]}"
        )
    assert True


async def test_create_object_users(session: AsyncSession):
    users = [
        Users(
            name="Данек",
            surname="Маклаков",
        ),
        Users(
            name="Гоша",
            surname="Фронек",
            email="phron@gmail.com",
        )
    ]

    session.add_all(users)
    await session.commit()

    print(f"Созданы пользователи с id: {[user.id for user in users]}")
    assert True


async def test_meetings_users_relationship(session: AsyncSession):
    users: list[Users] = [
        Users(
            name="Коляныч",
            surname="Бутовски"
        ),
        Users(
            name="Гоша",
            surname="Рубчинский"
        ),
        Users(
            name="Полина",
            surname="Рубчинский"
        ),
        Users(
            name="Юля",
            surname="Пидрюля",
            email="fsafsd@yandex.ru",
            additional_email=[
                "fdsfds@gmail.com",
                "gdsobh@yandex.ru"
            ]
        ),
    ]
    meetings: list[Meetings] = [
        Meetings(
            name="Встреча 1",
            description="Крутая встреча",
            link="https://telemost",
            duration="01:30",
            data_range=[
                [
                    "2026-12-21Т22:00:00Z",
                    "2026-12-22Т02:00:00Z"
                ],
                [
                    "2026-12-22Т22:00:00Z",
                    "2026-12-23Т02:00:00Z"
                ],
                [
                    "2026-12-24Т22:00:00Z",
                    "2026-12-25Т02:00:00Z"
                ]
            ]),
        Meetings(
            name="Встреча 2",
            description="Крутая встреча",
            link="https://telemost",
            duration="02:00",
            data_range=[
                [
                    "2026-12-21Т22:00:00Z",
                    "2026-12-22Т02:00:00Z"
                ],
                [
                    "2026-12-22Т22:00:00Z",
                    "2026-12-23Т02:00:00Z"
                ],
                [
                    "2026-12-24Т22:00:00Z",
                    "2026-12-25Т02:00:00Z"
                ]
            ]),
    ]

    meetings[0].owner = users[0]
    meetings[1].owner = users[0]
    meetings[0].participants.append(users[1])
    meetings[0].participants.append(users[2])
    meetings[1].participants.append(users[2])
    meetings[1].participants.append(users[3])

    session.add_all(meetings)
    session.add_all(users)
    await session.commit()

    assert meetings[0] in users[0].meetings_owner
    assert meetings[1] in users[0].meetings_owner
    assert users[1] in meetings[0].participants
    assert users[1] not in meetings[1].participants
    assert users[2] in meetings[0].participants
    assert users[3] in meetings[1].participants


async def test_create_object_teams(session):
    users: list[Users] = [
        Users(
            id=1,
            name="Коляныч",
            surname="Бутовски"
        ),
        Users(
            id=2,
            name="Гоша",
            surname="Рубчинский"
        ),
        Users(
            id=3,
            name="Юля",
            surname="Пидрюля",
            email="fsafsd@yandex.ru",
            additional_email=[
                "fdsfds@gmail.com",
                "gdsobh@yandex.ru"
            ]
        ),
    ]

    teams: list[Teams] = [
        Teams(
            id=1,
            name="Стилеру",
            description="Классное описание",
            emails=[
                "dfsafsd@gmail.com",
                "dan@yandex.ru",
                "fsdabfg@mail.com"
            ],
            user_id=1
        ),
        Teams(
            id=2,
            name="Топовая организация",
            description="Классное описание",
            user_id=1
        ),
        Teams(
            id=3,
            name="Студенческая организация",
            description="Классное описание",
            emails=[
                "asdf@gmail.com",
                "kirill@yandex.ru",
                "kolya@mail.com"
            ],
            user_id=3
        ),
    ]

    session.add_all(teams + users)
    await session.commit()

    query = select(Teams)
    result = await session.execute(query)
    teams = result.scalars().all()

    for team in teams:
        assert team.name in (
            "Стилеру", "Студенческая организация", "Топовая организация"
            )

    query = select(Users).options(selectinload(Users.teams))
    result = await session.execute(query)
    users: list[Users] = result.scalars().all()

    assert not users[1].teams
    assert teams[0] in users[0].teams
    assert teams[1] in users[0].teams
    assert teams[2] not in users[0].teams
    assert teams[2] in users[2].teams


async def test_meetings_teams_relationship(session):
    users: list[Users] = [
        Users(
            id=0,
            name="Коляныч",
            surname="Бутовски"
        ),
        Users(
            id=1,
            name="Гоша",
            surname="Рубчинский"
        ),
        Users(
            id=2,
            name="Юля",
            surname="Пидрюля",
            email="fsafsd@yandex.ru",
            additional_email=[
                "fdsfds@gmail.com",
                "gdsobh@yandex.ru"
            ]
        ),
    ]
    teams: list[Teams] = [
        Teams(
            id=0,
            name="Стилеру",
            description="Классное описание",
            emails=[
                "dfsafsd@gmail.com",
                "dan@yandex.ru",
                "fsdabfg@mail.com"
            ],
            user_id=0
        ),
        Teams(
            id=1,
            name="Топовая организация",
            description="Классное описание",
            user_id=0
        ),
        Teams(
            id=2,
            name="Студенческая организация",
            description="Классное описание",
            emails=[
                "asdf@gmail.com",
                "kirill@yandex.ru",
                "kolya@mail.com"
            ],
            user_id=2
        ),
    ]
    meetings = [
        Meetings(
            name="Встреча 1",
            description="Крутая встреча",
            link="https://telemost",
            duration="01:30",
            data_range=[
                [
                    "2026-12-21Т22:00:00Z",
                    "2026-12-22Т02:00:00Z"
                ],
                [
                    "2026-12-22Т22:00:00Z",
                    "2026-12-23Т02:00:00Z"
                ],
                [
                    "2026-12-24Т22:00:00Z",
                    "2026-12-25Т02:00:00Z"
                ]
            ]),
        Meetings(
            name="Встреча 2",
            description="Топовая встреча",
            link="https://telemost",
            duration="01:00",
            data_range=[
                [
                    "2026-12-22Т22:00:00Z",
                    "2026-12-23Т02:00:00Z"
                ],
                [
                    "2026-12-23Т22:00:00Z",
                    "2026-12-24Т02:00:00Z"
                ],
                [
                    "2026-12-25Т22:00:00Z",
                    "2026-12-26Т02:00:00Z"
                ]
            ]),
        Meetings(
            name="Встреча 3",
            description="Офигенная встреча",
            link="https://telemost",
            duration="03:00",
            data_range=[
                [
                    "2026-12-22Т22:00:00Z",
                    "2026-12-23Т02:00:00Z"
                ],
                [
                    "2026-12-23Т22:00:00Z",
                    "2026-12-24Т02:00:00Z"
                ],
                [
                    "2026-12-25Т22:00:00Z",
                    "2026-12-26Т02:00:00Z"
                ]
            ])
    ]

    meetings[0].team = teams[0]
    meetings[1].team = teams[2]
    meetings[2].team = teams[2]

    session.add_all(meetings + teams + users)
    await session.commit()

    teams_0 = (await session.execute(
        select(Teams)
        .options(selectinload(Teams.meetings))
        .where(Teams.id == 0)
    )).scalar()
    teams_1 = (await session.execute(
        select(Teams)
        .options(selectinload(Teams.meetings))
        .where(Teams.id == 1)
    )).scalar()
    teams_2 = (await session.execute(
        select(Teams)
        .options(selectinload(Teams.meetings))
        .where(Teams.id == 2)
    )).scalar()

    meetings_0 = (await session.execute(
        select(Meetings)
        .options(selectinload(Meetings.team))
        .where(Meetings.name == "Встреча 1")
    )).scalar()
    meetings_1 = (await session.execute(
        select(Meetings)
        .options(selectinload(Meetings.team))
        .where(Meetings.name == "Встреча 2")
    )).scalar()
    meetings_2 = (await session.execute(
        select(Meetings)
        .options(selectinload(Meetings.team))
        .where(Meetings.name == "Встреча 3")
    )).scalar()

    assert meetings_0 in teams_0.meetings
    assert meetings_1 not in teams_0.meetings
    assert len(teams_2.meetings) == 2
    assert meetings_2 in teams_2.meetings
    assert not teams_1.meetings
